"""VM security scan service.

Scans each VM's IPs using nmap (active port + version detection) and looks up
CVEs via the NVD API (NIST). No dependency on Shodan.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.vm.security_repo import VmSecurityRepo
from app.services.discord import notify_security_cve_alert

logger = logging.getLogger(__name__)

_NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_scan_event: asyncio.Event | None = None
_nvd_semaphore: asyncio.Semaphore | None = None

_scan_status: dict[str, Any] = {
    "running": False,
    "total": 0,
    "scanned": 0,
    "current_vm": None,
    "current_ip": None,
}


def get_scan_event() -> asyncio.Event:
    global _scan_event
    if _scan_event is None:
        _scan_event = asyncio.Event()
    return _scan_event


def _get_nvd_semaphore() -> asyncio.Semaphore:
    global _nvd_semaphore
    if _nvd_semaphore is None:
        _nvd_semaphore = asyncio.Semaphore(3)
    return _nvd_semaphore


def request_scan() -> None:
    """Signal the background security loop to run a scan immediately."""
    get_scan_event().set()


def get_scan_status() -> dict[str, Any]:
    return dict(_scan_status)


# ─── nmap ────────────────────────────────────────────────────────────────────

async def _nmap_scan(ip: str) -> dict[str, Any]:
    """Run nmap TCP connect + version detection + SSL cert extraction."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "nmap", "-sT", "-sV", "-p", "1-65535", "--open", "-T4", "-n",
            "--max-retries", "1", "--host-timeout", "90s",
            "--script", "ssl-cert",
            "-oX", "-", ip,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=150)
        return _parse_nmap_xml(stdout.decode(), ip)
    except FileNotFoundError:
        logger.warning("nmap not found")
        return {"ports": [], "cpes": [], "hostnames": []}
    except Exception as exc:
        logger.warning("nmap scan failed ip=%s: %s", ip, exc)
        return {"ports": [], "cpes": [], "hostnames": []}


def _parse_nmap_xml(xml_output: str, ip: str) -> dict[str, Any]:
    """Parse nmap XML output into ports, CPEs and hostnames."""
    try:
        root = ET.fromstring(xml_output)
    except ET.ParseError as exc:
        logger.warning("nmap XML parse error ip=%s: %s", ip, exc)
        return {"ports": [], "cpes": [], "hostnames": []}

    ports: list[dict[str, Any]] = []
    cpe_set: dict[str, str] = {}  # cpe_string → confidence

    host = root.find("host")
    if host is None:
        return {"ports": [], "cpes": [], "hostnames": []}

    # Reverse DNS via socket PTR
    hostnames: set[str] = set()
    try:
        name, _, _ = socket.gethostbyaddr(ip)
        if name and name != ip:
            hostnames.add(name)
    except Exception:
        pass

    for port_el in host.findall("ports/port"):
        state_el = port_el.find("state")
        if state_el is None or state_el.get("state") != "open":
            continue

        portid = int(port_el.get("portid", 0))
        service_el = port_el.find("service")

        service_banner = ""
        if service_el is not None:
            product = service_el.get("product", "")
            version = service_el.get("version", "")
            service_banner = f"{product} {version}".strip()
            conf_raw = int(service_el.get("conf", "0"))
            svc_confidence = "confirmed" if conf_raw >= 8 else "unverified"

            for cpe_el in service_el.findall("cpe"):
                cpe_str = (cpe_el.text or "").strip()
                if cpe_str:
                    # Keep highest confidence if CPE appears on multiple ports
                    existing = cpe_set.get(cpe_str, "unverified")
                    if svc_confidence == "confirmed" or existing == "unverified":
                        cpe_set[cpe_str] = svc_confidence
        else:
            svc_confidence = "confirmed"

        # SSL cert script — extract CN and SANs for hostnames
        for script_el in port_el.findall("script[@id='ssl-cert']"):
            cn_el = script_el.find("table[@key='subject']/elem[@key='commonName']")
            if cn_el is not None and cn_el.text:
                hostnames.add(cn_el.text.strip())
            for ext_el in script_el.findall("table[@key='extensions']/table"):
                name_el = ext_el.find("elem[@key='name']")
                val_el  = ext_el.find("elem[@key='value']")
                if (name_el is not None and "Subject Alternative Name" in (name_el.text or "")
                        and val_el is not None and val_el.text):
                    for san in val_el.text.split(","):
                        san = san.strip()
                        if san.startswith("DNS:"):
                            hostnames.add(san[4:].strip())

        entry: dict[str, Any] = {"port": portid, "confidence": svc_confidence}
        if service_banner:
            entry["service"] = service_banner
        ports.append(entry)

    cpes = [{"cpe": c, "confidence": conf} for c, conf in cpe_set.items()]
    return {"ports": ports, "cpes": cpes, "hostnames": sorted(hostnames)}


# ─── NVD CVE lookup ──────────────────────────────────────────────────────────

async def _fetch_nvd_cves(client: httpx.AsyncClient, cpe: str) -> list[dict[str, Any]]:
    """Fetch CVEs from NVD for a given CPE string (no API key required)."""
    async with _get_nvd_semaphore():
        try:
            params = {"cpeName": cpe, "noRejected": "", "resultsPerPage": 20}
            r = await client.get(_NVD_URL, params=params, timeout=15.0)
            if r.status_code == 403:
                logger.warning("nvd rate limit hit, sleeping 30s")
                await asyncio.sleep(30)
                return []
            if r.status_code != 200:
                return []
            return r.json().get("vulnerabilities", [])
        except Exception as exc:
            logger.warning("nvd fetch failed cpe=%s: %s", cpe, exc)
            return []


def _parse_nvd_cvss(cve_node: dict[str, Any]) -> float:
    """Extract the highest CVSS base score from an NVD CVE node."""
    metrics = cve_node.get("metrics", {})
    best = 0.0
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        for entry in metrics.get(key, []):
            score = entry.get("cvssData", {}).get("baseScore")
            if score is not None:
                try:
                    best = max(best, float(score))
                except (ValueError, TypeError):
                    pass
    return best


def _extract_nvd_entry(vuln: dict[str, Any], scanned_at: datetime) -> dict[str, Any] | None:
    cve_node = vuln.get("cve", {})
    cve_id = cve_node.get("id", "")
    score = _parse_nvd_cvss(cve_node)
    published_raw = cve_node.get("published", "")[:10]

    if score < 8.0:
        return None

    this_week = False
    try:
        pub_dt = datetime.fromisoformat(published_raw).replace(tzinfo=timezone.utc)
        if scanned_at.tzinfo is None:
            scanned_at = scanned_at.replace(tzinfo=timezone.utc)
        this_week = scanned_at.isocalendar()[:2] == pub_dt.isocalendar()[:2]
    except Exception:
        pass

    return {"id": cve_id, "score": score, "published": published_raw, "this_week": this_week}


# ─── Full IP scan ─────────────────────────────────────────────────────────────

async def _scan_ip(client: httpx.AsyncClient, ip: str, scanned_at: datetime) -> dict[str, Any]:
    """Scan a single IP with nmap and look up CVEs via NVD."""
    nmap = await _nmap_scan(ip)

    ports: list[dict[str, Any]] = nmap["ports"]
    cpes: list[dict[str, str]] = nmap["cpes"]
    hostnames: list[str] = nmap["hostnames"]

    # Deduplicate CPEs before querying NVD
    unique_cpes = list({c["cpe"] for c in cpes})
    vuln_lists = await asyncio.gather(*[_fetch_nvd_cves(client, cpe) for cpe in unique_cpes])

    seen_ids: set[str] = set()
    critical_cves: list[dict[str, Any]] = []
    for vulns in vuln_lists:
        for vuln in vulns:
            entry = _extract_nvd_entry(vuln, scanned_at)
            if entry and entry["id"] not in seen_ids:
                seen_ids.add(entry["id"])
                critical_cves.append(entry)

    return {
        "ip": ip,
        "ports": ports,
        "hostnames": hostnames,
        "cpes": cpes,
        "cves": critical_cves,
    }


# ─── Scan loop ───────────────────────────────────────────────────────────────

async def run_security_scan(db: AsyncSession) -> None:
    """Scan all VMs with assigned IPs and persist the results."""
    global _scan_status
    repo = VmSecurityRepo(db)
    vms = await repo.list_vms_with_ips()
    if not vms:
        return

    vms_with_ip = [vm for vm in vms if vm.get("ipv4")]
    scanned_at = datetime.now(tz=timezone.utc)
    _scan_status = {"running": True, "total": len(vms_with_ip), "scanned": 0, "current_vm": None, "current_ip": None}
    logger.info("security scan started for %d VMs at %s", len(vms_with_ip), scanned_at.isoformat())

    try:
        async with httpx.AsyncClient() as client:
            for vm in vms_with_ip:
                vm_id: int = vm["vm_id"]
                vm_name: str = vm.get("name", str(vm_id))
                ip: str = vm["ipv4"]
                _scan_status["current_vm"] = vm_name
                _scan_status["current_ip"] = ip
                try:
                    finding = await _scan_ip(client, ip, scanned_at)
                    await repo.save_scan(vm_id, [finding], scanned_at)
                    await db.commit()
                    weekly = [c for c in finding.get("cves", []) if c.get("this_week")]
                    if weekly:
                        await notify_security_cve_alert(
                            vm_id=vm_id,
                            vm_name=vm_name,
                            ip=ip,
                            cves=weekly,
                        )
                except Exception:
                    logger.exception("security scan failed for vm_id=%d", vm_id)
                    await db.rollback()
                finally:
                    _scan_status["scanned"] += 1
    finally:
        _scan_status = {"running": False, "total": len(vms_with_ip), "scanned": len(vms_with_ip), "current_vm": None, "current_ip": None}
        logger.info("security scan completed for %d VMs", len(vms_with_ip))
