"""
VM console endpoints (termproxy and WebSocket terminal proxy).

Provides a REST endpoint to obtain a Proxmox termproxy ticket and a
WebSocket endpoint that bidirectionally proxies the VNC-over-WebSocket
terminal stream between the browser client and the Proxmox node.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
from urllib.parse import quote, urlparse

logger = logging.getLogger(__name__)

import websockets
import websockets.exceptions
from fastapi import APIRouter, Depends, HTTPException, WebSocket, status
from fastapi.websockets import WebSocketState

from app.auth import AuthCtx, require_user
from app.auth.context import build_auth_ctx
from app.core.config import get_settings
from app.core.security.token import TokenService
from app.core.sessions import get_session_store
from app.db.core.engine import get_session_factory
from app.db.repositories.vm import VmAccessRepo
from app.services.proxmox.errors import ProxmoxError
from app.services.proxmox.executor import run_in_proxmox_executor
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
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.SHARED)
    gateway = get_proxmox_gateway()
    try:
        info = await run_in_proxmox_executor(gateway.termproxy, vm_id=vm_id)
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


def _check_vm_access_sync(vm_id: int, user_id: str, is_admin: bool) -> bool:
    """
    Synchronously check whether a user has any access level on a VM.

    Administrators are always granted access without a database query.  For
    regular users a new database session is opened, queried, and closed.

    This function is intended to be called via :func:`asyncio.to_thread` from
    an async context so that the blocking database call does not block the
    event loop.

    :param vm_id: Numeric identifier of the target VM.
    :param user_id: Identifier of the user to check.
    :param is_admin: Whether the user has administrator privileges.
    :returns: ``True`` if the user is an admin or has any access to the VM,
        ``False`` otherwise.
    :rtype: bool
    """
    if is_admin:
        return True
    db = get_session_factory()()
    try:
        return VmAccessRepo(db).has_vm_access(vm_id=vm_id, user_id=user_id, owner_only=False)
    finally:
        db.close()


async def _ws_auth(websocket: WebSocket) -> AuthCtx | None:
    """
    Authenticate a WebSocket connection using the session cookie.

    Reads the session cookie from the incoming WebSocket handshake, retrieves
    the associated access token from the session store, decodes it, and builds
    an :class:`~app.auth.context.AuthCtx` from the token payload.

    :param websocket: The incoming WebSocket connection to authenticate.
    :returns: An :class:`~app.auth.context.AuthCtx` instance if authentication
        succeeds, or ``None`` if the session cookie is missing, the token is
        not found, or decoding fails.
    :rtype: AuthCtx | None
    """
    settings = get_settings()
    session_id = websocket.cookies.get(settings.session_cookie_name)
    if not session_id:
        return None
    try:
        store = get_session_store()
        access_token = store.get_access_token(session_id)
        if not access_token:
            return None
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
    await websocket.accept()

    ctx = await _ws_auth(websocket)
    if ctx is None:
        await websocket.close(code=4401, reason="Unauthorized")
        return

    allowed = await asyncio.to_thread(_check_vm_access_sync, vm_id, ctx.user_id, ctx.is_admin)
    if not allowed:
        await websocket.close(code=4403, reason="Forbidden")
        return

    settings = get_settings()
    gateway = get_proxmox_gateway()

    try:
        info = await run_in_proxmox_executor(gateway.termproxy, vm_id=vm_id)
    except ProxmoxError as exc:
        await websocket.close(code=4503, reason=str(exc))
        return

    node = info["node"]
    port = info["port"]
    ticket = info["ticket"]
    username = info["username"]

    encoded_ticket = quote(ticket, safe="")
    parsed = urlparse(settings.proxmox_base_url)
    ws_scheme = "wss" if parsed.scheme == "https" else "ws"
    host_port = parsed.hostname
    if parsed.port:
        host_port = f"{host_port}:{parsed.port}"
    wss_url = f"{ws_scheme}://{host_port}/api2/json/nodes/{node}/qemu/{vm_id}/vncwebsocket?port={port}&vncticket={encoded_ticket}"

    ssl_ctx = _proxmox_ssl_context(settings.proxmox_verify_tls)

    pve_ticket = gateway.get_pve_auth_ticket()
    pve_service = settings.proxmox_service or "PVE"
    cookie_header = f"{pve_service}AuthCookie={pve_ticket}"

    logger.info("terminal_ws vm=%s proxmox_node=%s port=%s", vm_id, node, port)

    try:
        async with websockets.connect(
            wss_url,
            ssl=ssl_ctx,
            additional_headers={"Cookie": cookie_header},
            subprotocols=["binary"],
        ) as prox_ws:
            logger.info("terminal_ws vm=%s connected to proxmox, sending auth", vm_id)
            await prox_ws.send(f"{username}:{ticket}\n".encode())

            async def from_client() -> None:
                """
                Forward raw bytes from the browser client to the Proxmox WebSocket.

                Runs until the client WebSocket closes or an exception occurs.
                """
                try:
                    async for data in websocket.iter_bytes():
                        await prox_ws.send(data)
                except Exception as exc:
                    logger.debug("terminal_ws vm=%s from_client closed: %s", vm_id, exc)

            async def from_proxmox() -> None:
                """
                Forward messages from the Proxmox WebSocket to the browser client.

                Binary messages are forwarded as bytes; text messages are forwarded
                as text.  Runs until the Proxmox WebSocket closes or an exception
                occurs.
                """
                try:
                    async for msg in prox_ws:
                        if isinstance(msg, bytes):
                            await websocket.send_bytes(msg)
                        else:
                            await websocket.send_text(msg)
                except Exception as exc:
                    logger.debug("terminal_ws vm=%s from_proxmox closed: %s", vm_id, exc)

            t1 = asyncio.create_task(from_client())
            t2 = asyncio.create_task(from_proxmox())
            _, pending = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()

    except Exception as exc:
        logger.warning("terminal_ws vm=%s proxmox connection failed: %r", vm_id, exc)
    finally:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
