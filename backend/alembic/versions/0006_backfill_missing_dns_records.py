"""backfill missing DNS A/AAAA records

For VMs that have an IPv4 or IPv6 but no corresponding A/AAAA record
in the PowerDNS ``records`` table, insert the missing records.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-23

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# --- wordgen logic inlined to keep migration self-contained ---------------
import hashlib

_ADJECTIVES = [
    "amber","arctic","azure","bold","brave","bright","calm","cedar","clear",
    "cool","crisp","cyber","dark","deep","distant","electric","elegant",
    "emerald","epic","faint","fast","fierce","fresh","frozen","gentle",
    "golden","grand","happy","hollow","humble","icy","jade","keen","lively",
    "lunar","mighty","misty","noble","polar","prime","proud","quick","quiet",
    "radiant","rapid","sharp","silent","silver","sleek","smart","solar",
    "solid","stark","stellar","still","stone","swift","tall","teal","vivid",
    "warm","wild","wise","zesty",
]
_NOUNS = [
    "anchor","arrow","atlas","aurora","beacon","blade","bolt","breeze",
    "bridge","byte","cloud","comet","coral","crane","crystal","dawn","delta",
    "dome","drift","eagle","echo","falcon","fern","fjord","flame","flare",
    "flux","forge","frost","gale","gem","grove","hawk","haven","helm","hive",
    "horizon","isle","kestrel","lake","lance","lark","leaf","light","lion",
    "lotus","lynx","maple","mesa","mist","moon","moss","oak","orbit","peak",
    "pine","pixel","prism","quartz","raven","reef","ridge","river","rock",
    "rover","sage","seal","slate","snow","spark","star","stone","stream",
    "summit","surf","swan","terra","tide","tower","trail","vault","vale",
    "wave","wind",
]

def _vm_dns_label(vm_id: int) -> str:
    digest = int(hashlib.sha256(str(vm_id).encode()).hexdigest(), 16)
    adj = _ADJECTIVES[digest % len(_ADJECTIVES)]
    noun = _NOUNS[(digest // len(_ADJECTIVES)) % len(_NOUNS)]
    return f"{adj}-{noun}"

# --------------------------------------------------------------------------

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Read DNS_ZONE from environment, fallback to default
import os
_DNS_ZONE = os.environ.get("DNS_ZONE", "h.lan").rstrip(".")


def upgrade() -> None:
    conn = op.get_bind()

    # Get the domain_id for our zone
    domain_row = conn.execute(
        sa.text("SELECT id FROM domains WHERE name = :zone"),
        {"zone": _DNS_ZONE},
    ).first()
    if domain_row is None:
        # Zone doesn't exist yet in PowerDNS — nothing to backfill
        return
    domain_id = domain_row[0]

    # Fetch all VMs with an IP address
    vms = conn.execute(
        sa.text("SELECT vm_id, host(ipv4) AS ipv4, host(ipv6) AS ipv6 FROM vms WHERE ipv4 IS NOT NULL OR ipv6 IS NOT NULL")
    ).fetchall()

    for vm in vms:
        vm_id, ipv4, ipv6 = vm[0], vm[1], vm[2]
        fqdn = f"{_vm_dns_label(vm_id)}.{_DNS_ZONE}"

        if ipv4:
            exists = conn.execute(
                sa.text("SELECT 1 FROM records WHERE name = :name AND type = 'A' LIMIT 1"),
                {"name": fqdn},
            ).first()
            if not exists:
                conn.execute(
                    sa.text(
                        "INSERT INTO records (domain_id, name, type, content, ttl, disabled, auth) "
                        "VALUES (:domain_id, :name, 'A', :content, 300, false, true)"
                    ),
                    {"domain_id": domain_id, "name": fqdn, "content": ipv4},
                )

        if ipv6:
            exists = conn.execute(
                sa.text("SELECT 1 FROM records WHERE name = :name AND type = 'AAAA' LIMIT 1"),
                {"name": fqdn},
            ).first()
            if not exists:
                conn.execute(
                    sa.text(
                        "INSERT INTO records (domain_id, name, type, content, ttl, disabled, auth) "
                        "VALUES (:domain_id, :name, 'AAAA', :content, 300, false, true)"
                    ),
                    {"domain_id": domain_id, "name": fqdn, "content": ipv6},
                )


def downgrade() -> None:
    # Data migration — no safe automatic rollback
    pass
