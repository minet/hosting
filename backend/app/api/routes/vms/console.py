"""
VM console endpoints (termproxy and WebSocket terminal proxy).

Provides a REST endpoint to obtain a Proxmox termproxy ticket and a
WebSocket endpoint that bidirectionally proxies the VNC-over-WebSocket
terminal stream between the browser client and the Proxmox node.

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
from urllib.parse import quote, urlparse

logger = logging.getLogger(__name__)


def _mux_encode(channel: int, payload: bytes) -> bytes:
    """Encode a mux frame: ``channel:len:payload``."""
    return f"{channel}:{len(payload)}:".encode() + payload


def _mux_decode(data: bytes) -> tuple[int, bytes] | None:
    """Decode one mux frame from *data*. Returns ``(channel, payload)`` or ``None``."""
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

import websockets
import websockets.exceptions
from fastapi import APIRouter, Depends, WebSocket
from fastapi.websockets import WebSocketState

from app.auth import AuthCtx, require_user

# Track active terminal sessions per VM: vm_id -> user_id
# NOTE: This is process-local — only works with a single uvicorn worker.
# With multiple workers, two users could open terminals on the same VM.
_active_terminals: dict[int, str] = {}
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

router = APIRouter()


# ---------------------------------------------------------------------------
# REST — get termproxy ticket
# ---------------------------------------------------------------------------


@router.post("/{vm_id}/termproxy")
async def get_termproxy(
    vm_id: int,
    ctx: AuthCtx = Depends(require_user),
    access: VmAccessService = Depends(get_vm_access_service),
) -> dict:
    """
    Return a Proxmox termproxy ticket for the given VM.

    The caller must have at least shared access to the VM.

    :param vm_id: Numeric identifier of the target VM.
    :param ctx: Authenticated user context (injected).
    :param access: VM access service used to enforce minimum access level (injected).
    :returns: Dictionary containing ``vm_id``, ``node``, ``port``, ``ticket``, and ``upid``.
    :rtype: dict
    :raises HTTPException: With status 403 if the caller has no access to the VM,
        or with an appropriate status if the Proxmox API is unreachable.
    """
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


def _proxmox_ssl_context(verify: bool) -> ssl.SSLContext | None:
    """
    Build an SSL context suitable for connecting to the Proxmox WebSocket endpoint.

    When *verify* is ``True`` the default SSL verification behaviour is used
    (returns ``None`` so that :func:`websockets.connect` performs normal checks).
    When *verify* is ``False`` a permissive context that disables hostname and
    certificate verification is returned.

    :param verify: Whether to verify the Proxmox TLS certificate.
    :returns: A configured :class:`ssl.SSLContext` instance, or ``None`` when
        standard verification is acceptable.
    :rtype: ssl.SSLContext | None
    """
    if verify:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def _check_vm_access(vm_id: int, user_id: str, is_admin: bool) -> bool:
    """
    Asynchronously check whether a user has any access level on a VM.

    Administrators are always granted access without a database query.  For
    regular users a new async database session is opened, queried, and closed.

    :param vm_id: Numeric identifier of the target VM.
    :param user_id: Identifier of the user to check.
    :param is_admin: Whether the user has administrator privileges.
    :returns: ``True`` if the user is an admin or has any access to the VM,
        ``False`` otherwise.
    :rtype: bool
    """
    if is_admin:
        return True
    async with get_session_factory()() as db:
        return await VmAccessRepo(db).has_vm_access(vm_id=vm_id, user_id=user_id, owner_only=False)


async def _ws_auth(websocket: WebSocket) -> AuthCtx | None:
    """Authenticate a WebSocket connection using the access token cookie."""
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


@router.websocket("/{vm_id}/terminal")
async def terminal_ws(vm_id: int, websocket: WebSocket) -> None:
    """
    WebSocket endpoint that proxies a Proxmox VNC terminal session.

    Accepts the WebSocket connection, authenticates the caller via the session
    cookie, checks VM access, obtains a fresh termproxy ticket from Proxmox, and
    then bridges data bidirectionally between the client WebSocket and the
    Proxmox VNC WebSocket until either side disconnects.

    Closes the WebSocket with an appropriate application-level error code when:

    * The caller is not authenticated (code 4401).
    * The caller has no access to the VM (code 4403).
    * The Proxmox termproxy call fails (code 4503).

    :param vm_id: Numeric identifier of the VM whose terminal to proxy.
    :param websocket: The incoming client WebSocket connection.
    :returns: None
    """
    await websocket.accept(subprotocol="binary")

    ctx = await _ws_auth(websocket)
    if ctx is None:
        await websocket.close(code=4401, reason="Unauthorized")
        return

    allowed = await _check_vm_access(vm_id, ctx.user_id, ctx.is_admin)
    if not allowed:
        await websocket.close(code=4403, reason="Forbidden")
        return

    if vm_id in _active_terminals:
        await websocket.close(code=4409, reason="Console already in use")
        return

    _active_terminals[vm_id] = ctx.user_id

    try:
        settings = get_settings()
        gateway = get_proxmox_gateway()

        try:
            info = await asyncio.to_thread(gateway.termproxy_with_ticket, vm_id=vm_id)
        except ProxmoxError as exc:
            logger.warning("terminal_ws vm=%s termproxy failed: %s", vm_id, exc)
            await websocket.close(code=4503, reason=str(exc))
            return

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
        wss_url = f"{ws_scheme}://{host_port}/api2/json/nodes/{node}/qemu/{vm_id}/vncwebsocket?port={port}&vncticket={encoded_ticket}"

        ssl_ctx = _proxmox_ssl_context(settings.proxmox_verify_tls)

        service = settings.proxmox_service or "PVE"
        ws_auth_headers = {"Cookie": f"{service}AuthCookie={pve_ticket}"}

        logger.info("terminal_ws vm=%s proxmox_node=%s port=%s", vm_id, node, port)

        async with websockets.connect(
            wss_url,
            ssl=ssl_ctx,
            additional_headers=ws_auth_headers,
            subprotocols=["binary"],
        ) as prox_ws:
            logger.info("terminal_ws vm=%s connected to proxmox, sending auth", vm_id)
            await prox_ws.send(f"{username}:{ticket}\n".encode())

            async def from_client() -> None:
                try:
                    async for data in websocket.iter_bytes():
                        frame = _mux_decode(data)
                        if frame is None:
                            await prox_ws.send(data)
                        elif frame[0] == 0:
                            await prox_ws.send(frame[1])
                except Exception as exc:
                    logger.debug("terminal_ws vm=%s from_client closed: %s", vm_id, exc)

            _lone_lf = re.compile(rb'(?<!\r)\n')

            async def from_proxmox() -> None:
                try:
                    async for msg in prox_ws:
                        payload = msg if isinstance(msg, bytes) else msg.encode()
                        payload = _lone_lf.sub(b'\r\n', payload)
                        await websocket.send_bytes(_mux_encode(0, payload))
                except Exception as exc:
                    logger.warning("terminal_ws vm=%s from_proxmox error: %s", vm_id, exc)

            t1 = asyncio.create_task(from_client())
            t2 = asyncio.create_task(from_proxmox())
            _, pending = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()

    except Exception as exc:
        logger.warning("terminal_ws vm=%s proxmox connection failed: %r", vm_id, exc)
    finally:
        _active_terminals.pop(vm_id, None)
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
