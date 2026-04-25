"""VM security scan service.

Scans each VM's IPs using Shodan InternetDB (no API key required) and enriches
CVE entries via the CIRCL CVE API. Only CVEs with a CVSS score >= 8.0 that were
published in the same ISO calendar week as the scan date are stored.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.vm.security_repo import VmSecurityRepo
from app.services.discord import notify_security_cve_alert

logger = logging.getLogger(__name__)

_INTERNETDB_URL = "https://internetdb.shodan.io/{ip}"
_CIRCL_CVE_URL = "https://cve.circl.lu/api/cve/{cve_id}"
_scan_event: asyncio.Event | None = None
_cve_semaphore: asyncio.Semaphore | None = None


def get_scan_event() -> asyncio.Event:
    global _scan_event
    if _scan_event is None:
        _scan_event = asyncio.Event()
    return _scan_event


def _get_cve_semaphore() -> asyncio.Semaphore:
    global _cve_semaphore
    if _cve_semaphore is None:
        _cve_semaphore = asyncio.Semaphore(3)
    return _cve_semaphore


def request_scan() -> None:
    """Signal the background security loop to run a scan immediately."""
    get_scan_event().set()


async def _fetch_internetdb(client: httpx.AsyncClient, ip: str) -> dict[str, Any]:
    try:
        r = await client.get(_INTERNETDB_URL.format(ip=ip), timeout=10.0)
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logger.warning("internetdb fetch failed ip=%s: %s", ip, exc)
        return {}


async def _fetch_cve(client: httpx.AsyncClient, cve_id: str) -> dict[str, Any] | None:
    async with _get_cve_semaphore():
        try:
            r = await client.get(_CIRCL_CVE_URL.format(cve_id=cve_id), timeout=10.0)
            if r.status_code != 200:
                return None
            return r.json()
        except Exception as exc:
            logger.warning("circl cve fetch failed cve=%s: %s", cve_id, exc)
            return None


def _parse_cvss_score(cve_data: dict[str, Any]) -> float:
    """Extract the highest CVSS base score from CVE 5.1 or legacy CIRCL format."""
    # Legacy format (old CIRCL API)
    if "cvss" in cve_data and cve_data["cvss"] is not None:
        try:
            return float(cve_data["cvss"])
        except (ValueError, TypeError):
            pass

    # CVE 5.1 format — look in containers.cna.metrics and containers.adp[].metrics
    best = 0.0
    containers = cve_data.get("containers", {})
    sources = [containers.get("cna", {})] + containers.get("adp", [])
    for src in sources:
        for metric in src.get("metrics", []):
            for key in ("cvssV4_0", "cvssV3_1", "cvssV3_0", "cvssV2_0"):
                cvss = metric.get(key, {})
                score = cvss.get("baseScore")
                if score is not None:
                    try:
                        best = max(best, float(score))
                    except (ValueError, TypeError):
                        pass
    return best


def _parse_published(cve_data: dict[str, Any]) -> str:
    """Extract publication date from CVE 5.1 or legacy CIRCL format."""
    # CVE 5.1
    meta = cve_data.get("cveMetadata", {})
    if meta.get("datePublished"):
        return str(meta["datePublished"])[:10]
    # Legacy
    return str(cve_data.get("Published") or "")[:10]


def _extract_cve_entry(cve_data: dict[str, Any], scanned_at: datetime) -> dict[str, Any] | None:
    """Return a CVE entry dict for any CVE. Marks same-week + score >= 8 CVEs with `this_week: True` for Discord alerts."""
    cve_id = (cve_data.get("cveMetadata", {}).get("cveId") or cve_data.get("id", ""))
    score = _parse_cvss_score(cve_data)
    published = _parse_published(cve_data)

    this_week = False
    try:
        pub_dt = datetime.fromisoformat(published).replace(tzinfo=timezone.utc)
        if scanned_at.tzinfo is None:
            scanned_at = scanned_at.replace(tzinfo=timezone.utc)
        this_week = scanned_at.isocalendar()[:2] == pub_dt.isocalendar()[:2]
    except Exception:
        pass

    return {
        "id": cve_id,
        "score": score,
        "published": published,
        "this_week": this_week,
    }


async def _scan_ip(client: httpx.AsyncClient, ip: str, scanned_at: datetime) -> dict[str, Any]:
    """Scan a single IP and return its finding dict."""
    data = await _fetch_internetdb(client, ip)
    if not data:
        return {"ip": ip, "ports": [], "hostnames": [], "cves": []}

    cve_ids: list[str] = data.get("vulns") or []
    ports: list[int] = data.get("ports") or []
    hostnames: list[str] = data.get("hostnames") or []
    cpes: list[str] = data.get("cpes") or []

    cve_results = await asyncio.gather(*[_fetch_cve(client, cid) for cid in cve_ids])

    critical_cves = []
    for cve_data in cve_results:
        if not cve_data:
            continue
        entry = _extract_cve_entry(cve_data, scanned_at)
        if entry:
            critical_cves.append(entry)

    return {"ip": ip, "ports": ports, "hostnames": hostnames, "cpes": cpes, "cves": critical_cves}


async def run_security_scan(db: AsyncSession) -> None:
    """Scan all VMs with assigned IPs and persist the results."""
    repo = VmSecurityRepo(db)
    vms = await repo.list_vms_with_ips()
    if not vms:
        return

    scanned_at = datetime.now(tz=timezone.utc)
    logger.info("security scan started for %d VMs at %s", len(vms), scanned_at.isoformat())

    async with httpx.AsyncClient() as client:
        for vm in vms:
            vm_id: int = vm["vm_id"]
            ips = [ip for ip in [vm.get("ipv4")] if ip]
            if not ips:
                continue
            try:
                findings = await asyncio.gather(*[_scan_ip(client, ip, scanned_at) for ip in ips])
                findings_list = list(findings)
                await repo.save_scan(vm_id, findings_list, scanned_at)
                await db.commit()
                # Discord alert for same-week critical CVEs
                for finding in findings_list:
                    weekly = [c for c in finding.get("cves", []) if c.get("this_week")]
                    if weekly:
                        await notify_security_cve_alert(
                            vm_id=vm_id,
                            vm_name=vm.get("name", str(vm_id)),
                            ip=finding["ip"],
                            cves=weekly,
                        )
            except Exception:
                logger.exception("security scan failed for vm_id=%d", vm_id)
                await db.rollback()

    logger.info("security scan completed for %d VMs", len(vms))
