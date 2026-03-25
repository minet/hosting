"""
VM console endpoints (termproxy and WebSocket terminal proxy).

The backend maintains ONE Proxmox connection per VM.  Browser clients
attach/detach from that shared session so that Proxmox always sees a
single consumer on serial0.

Client ↔ backend uses a simple mux framing: ``channel:len:payload``
  - channel 0 = terminal data
  - channel 1 = resize (cols:rows), not forwarded to Proxmox

Backend ↔ Proxmox uses raw bytes (Proxmox vncwebsocket protocol).
"""

from __future__ import annotations

import asyncio
import logging
import re
import ssl
from dataclasses import dataclass, field
from urllib.parse import quote, urlparse

import websockets
import websockets.exceptions
from fastapi import APIRouter, Depends, WebSocket
from fastapi.websockets import WebSocketState

from app.auth import AuthCtx, require_user
from app.auth.context import build_auth_ctx
from app.core.config import get_settings
from app.core.security.token import TokenService
from app.core.sessions import get_access_token
from app.db.core.engine import get_session_factory
from app.db.repositories.vm import VmAccessRepo
from app.services.proxmox.errors import ProxmoxError
from app.services.proxmox.gateway import get_proxmox_gateway
from app.services.vm.access import AccessLevel, VmAccessService
from app.services.vm.deps import get_vm_access_service
from app.services.vm.errors import raise_proxmox_as_http

logger = logging.getLogger(__name__)

_lone_lf = re.compile(rb"(?<!\r)\n")

router = APIRouter()


# ---------------------------------------------------------------------------
# Mux helpers
# ---------------------------------------------------------------------------


def _mux_encode(channel: int, payload: bytes) -> bytes:
    return f"{channel}:{len(payload)}:".encode() + payload


def _mux_decode(data: bytes) -> tuple[int, bytes] | None:
    c1 = data.find(b":")
    if c1 == -1:
        return None
    c2 = data.find(b":", c1 + 1)
    if c2 == -1:
        return None
    try:
        channel = int(data[:c1])
        length = int(data[c1 + 1 : c2])
    except ValueError:
        return None
    start = c2 + 1
    if start + length > len(data):
        return None
    return channel, data[start : start + length]


# ---------------------------------------------------------------------------
# Shared Proxmox session per VM
# ---------------------------------------------------------------------------


@dataclass
class _VmSession:
    """A single Proxmox serial session shared by all browser clients."""

    vm_id: int
    prox_ws: websockets.WebSocketClientProtocol
    clients: set[WebSocket] = field(default_factory=set)
    _reader_task: asyncio.Task | None = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def start_reader(self) -> None:
        self._reader_task = asyncio.create_task(self._broadcast_from_proxmox())

    async def _broadcast_from_proxmox(self) -> None:
        """Read from Proxmox and broadcast to every attached client."""
        try:
            async for msg in self.prox_ws:
                payload = msg if isinstance(msg, bytes) else msg.encode()
                payload = _lone_lf.sub(b"\r\n", payload)
                frame = _mux_encode(0, payload)
                dead: list[WebSocket] = []
                for ws in list(self.clients):
                    try:
                        await ws.send_bytes(frame)
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    self.clients.discard(ws)
        except Exception as exc:
            logger.warning("_VmSession vm=%s proxmox reader stopped: %s", self.vm_id, exc)

    async def send_to_proxmox(self, data: bytes) -> None:
        await self.prox_ws.send(data)

    async def close(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
        try:
            await self.prox_ws.close()
        except Exception:
            pass


# vm_id -> session  (process-local, single worker)
_sessions: dict[int, _VmSession] = {}
_sessions_lock = asyncio.Lock()


def _proxmox_ssl_context(verify: bool) -> ssl.SSLContext | None:
    if verify:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def _get_or_create_session(vm_id: int) -> _VmSession:
    """Return an existing session or open a new Proxmox connection."""
    async with _sessions_lock:
        session = _sessions.get(vm_id)
        if session is not None:
            try:
                await session.prox_ws.ping()
                return session
            except Exception:
                logger.info("_get_or_create_session vm=%s stale session, reconnecting", vm_id)
                await session.close()
                _sessions.pop(vm_id, None)

        settings = get_settings()
        gateway = get_proxmox_gateway()

        info = await asyncio.to_thread(gateway.termproxy_with_ticket, vm_id=vm_id)

        node = info["node"]
        port = info["port"]
        ticket = info["ticket"]
        username = info["username"]
        pve_ticket = info["pve_ticket"]

        encoded_ticket = quote(ticket, safe="")
        parsed = urlparse(settings.proxmox_base_url)
        ws_scheme = "wss" if parsed.scheme == "https" else "ws"
        host_port = parsed.hostname
        if parsed.port:
            host_port = f"{host_port}:{parsed.port}"
        wss_url = (
            f"{ws_scheme}://{host_port}/api2/json/nodes/{node}/qemu/{vm_id}"
            f"/vncwebsocket?port={port}&vncticket={encoded_ticket}"
        )

        ssl_ctx = _proxmox_ssl_context(settings.proxmox_verify_tls)
        service = settings.proxmox_service or "PVE"
        ws_auth_headers = {"Cookie": f"{service}AuthCookie={pve_ticket}"}

        logger.info("_get_or_create_session vm=%s connecting proxmox node=%s port=%s", vm_id, node, port)

        prox_ws = await websockets.connect(
            wss_url,
            ssl=ssl_ctx,
            additional_headers=ws_auth_headers,
            subprotocols=["binary"],
            compression=None,
            ping_interval=None,
        )
        await prox_ws.send(f"{username}:{ticket}\n".encode())

        session = _VmSession(vm_id=vm_id, prox_ws=prox_ws)
        session.start_reader()
        _sessions[vm_id] = session
        return session


async def _release_client(vm_id: int, ws: WebSocket) -> None:
    """Detach a client. If no clients remain, tear down the Proxmox session."""
    async with _sessions_lock:
        session = _sessions.get(vm_id)
        if session is None:
            return
        session.clients.discard(ws)
        if not session.clients:
            logger.info("_release_client vm=%s no clients left, closing proxmox session", vm_id)
            await session.close()
            _sessions.pop(vm_id, None)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


async def _check_vm_access(vm_id: int, user_id: str, is_admin: bool) -> bool:
    if is_admin:
        return True
    async with get_session_factory()() as db:
        return await VmAccessRepo(db).has_vm_access(vm_id=vm_id, user_id=user_id, owner_only=False)


async def _ws_auth(websocket: WebSocket) -> AuthCtx | None:
    settings = get_settings()
    access_token = get_access_token(websocket)
    if not access_token:
        return None
    try:
        payload = TokenService(settings=settings).decode(access_token)
        return build_auth_ctx(payload, settings)
    except Exception:
        logger.warning("terminal_ws _ws_auth failed", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# REST — get termproxy ticket
# ---------------------------------------------------------------------------


@router.post("/{vm_id}/termproxy")
async def get_termproxy(
    vm_id: int,
    ctx: AuthCtx = Depends(require_user),
    access: VmAccessService = Depends(get_vm_access_service),
) -> dict:
    await access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.SHARED)
    gateway = get_proxmox_gateway()
    try:
        info = await asyncio.to_thread(gateway.termproxy, vm_id=vm_id)
    except ProxmoxError as exc:
        raise_proxmox_as_http(exc, unavailable="Unable to get terminal ticket from Proxmox")
    return {
        "vm_id": vm_id,
        "node": info["node"],
        "port": info["port"],
        "ticket": info["ticket"],
        "upid": info["upid"],
    }


# ---------------------------------------------------------------------------
# WebSocket — proxied terminal
# ---------------------------------------------------------------------------


@router.websocket("/{vm_id}/terminal")
async def terminal_ws(vm_id: int, websocket: WebSocket) -> None:
    await websocket.accept(subprotocol="binary")

    ctx = await _ws_auth(websocket)
    if ctx is None:
        await websocket.close(code=4401, reason="Unauthorized")
        return

    allowed = await _check_vm_access(vm_id, ctx.user_id, ctx.is_admin)
    if not allowed:
        await websocket.close(code=4403, reason="Forbidden")
        return

    try:
        session = await _get_or_create_session(vm_id)
    except ProxmoxError as exc:
        logger.warning("terminal_ws vm=%s termproxy failed: %s", vm_id, exc)
        await websocket.close(code=4503, reason=str(exc))
        return
    except Exception as exc:
        logger.warning("terminal_ws vm=%s proxmox connection failed: %r", vm_id, exc)
        await websocket.close(code=4503, reason="Proxmox connection failed")
        return

    session.clients.add(websocket)
    logger.info("terminal_ws vm=%s client attached (%d total)", vm_id, len(session.clients))

    try:
        async for data in websocket.iter_bytes():
            frame = _mux_decode(data)
            if frame is None:
                await session.send_to_proxmox(data)
            elif frame[0] == 0:
                await session.send_to_proxmox(frame[1])
            # channel 1 (resize) — ignored
    except Exception as exc:
        logger.debug("terminal_ws vm=%s client disconnected: %s", vm_id, exc)
    finally:
        await _release_client(vm_id, websocket)
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
