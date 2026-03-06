"""
Access-token decoding and validation module.

Provides :class:`TokenService` which validates Keycloak-issued JWTs,
and FastAPI dependency helpers for extracting the token payload from
incoming requests.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from jwcrypto.common import JWException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from keycloak import KeycloakOpenID
from keycloak.exceptions import KeycloakError

from app.core.config import Settings, get_settings
from app.core.sessions import get_session_store

TokenPayload = dict[str, Any]
http_bearer = HTTPBearer(auto_error=False)


class TokenService:
    """Decode and validate access tokens from a Bearer header or backend session.

    Validates the JWT signature via the Keycloak public key set and enforces
    issuer and audience claims.
    """

    def __init__(self, *, settings: Settings):
        """Initialise the token service with application settings.

        :param settings: Application settings containing Keycloak configuration.
        :type settings: Settings
        """
        self._settings = settings
        self._keycloak = KeycloakOpenID(
            server_url=settings.keycloak_server_url,
            realm_name=settings.keycloak_realm,
            client_id=settings.keycloak_client_id,
            client_secret_key=settings.keycloak_client_secret,
            verify=settings.keycloak_verify_tls,
        )

    def decode(self, token: str) -> TokenPayload:
        """Decode and validate a JWT access token.

        :param token: The raw JWT string.
        :type token: str
        :returns: The decoded token claims.
        :rtype: TokenPayload
        :raises HTTPException: If the token is invalid, expired, or fails
            issuer/audience checks (HTTP 401).
        """
        try:
            payload = self._keycloak.decode_token(token=token, validate=True)
        except (KeycloakError, JWException, ValueError, TypeError) as exc:
            raise self._unauthorized(reason=type(exc).__name__) from exc

        if not isinstance(payload, dict):
            raise self._unauthorized(reason=f"payload_type={type(payload).__name__}")

        self._enforce_issuer_and_audience(payload)
        return payload

    def from_request(
        self,
        *,
        request: Request,
        credentials: HTTPAuthorizationCredentials | None,
    ) -> TokenPayload:
        """Extract and decode a token from an HTTP request.

        Checks, in order:

        1. A ``Bearer`` token in the ``Authorization`` header.
        2. An access token stored in a backend session cookie.

        :param request: The incoming FastAPI request.
        :type request: Request
        :param credentials: Optional HTTP Bearer credentials extracted by FastAPI.
        :type credentials: HTTPAuthorizationCredentials | None
        :returns: The decoded token claims.
        :rtype: TokenPayload
        :raises HTTPException: If no valid token is found (HTTP 401) or the
            session store is unavailable (HTTP 503).
        """
        if credentials is not None and credentials.scheme.lower() == "bearer":
            return self.decode(credentials.credentials)

        session_id = request.cookies.get(self._settings.session_cookie_name)
        if session_id:
            session_store = get_session_store()
            try:
                access_token = session_store.get_access_token(session_id)
                id_token = session_store.get_id_token(session_id) if not access_token else None
            except RuntimeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication session storage unavailable",
                ) from exc

            if access_token:
                return self.decode(access_token)

            if id_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session missing access token for API authorization",
                )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token or access token session",
        )

    def _unauthorized(self, *, reason: str | None = None) -> HTTPException:
        """Build an HTTP 401 exception, optionally including a debug reason.

        :param reason: Extra detail appended to the message when debug mode is on.
        :type reason: str | None
        :returns: An ``HTTPException`` with status 401.
        :rtype: HTTPException
        """
        detail = "Invalid or expired token"
        if self._settings.app_debug and reason:
            detail = f"{detail} ({reason})"
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

    def _expected_issuer(self) -> str:
        """Return the expected token issuer URL with trailing slash stripped.

        :returns: The normalised issuer URL.
        :rtype: str
        """
        return self._settings.keycloak_issuer.rstrip("/")

    @staticmethod
    def _extract_audiences(payload: TokenPayload) -> set[str]:
        """Extract the set of audiences from a token payload.

        Handles both single-string and list-of-strings ``aud`` claims.

        :param payload: The decoded JWT claims.
        :type payload: TokenPayload
        :returns: A set of audience strings (may be empty).
        :rtype: set[str]
        """
        aud_claim = payload.get("aud")
        if isinstance(aud_claim, str):
            return {aud_claim}
        if isinstance(aud_claim, list):
            return {str(item) for item in aud_claim}
        return set()

    @classmethod
    def _token_targets_client(cls, payload: TokenPayload, client_id: str) -> bool:
        """Determine whether a token is intended for the given client.

        Checks the ``aud`` claim, the ``azp`` claim, and the
        ``resource_access`` dictionary.

        :param payload: The decoded JWT claims.
        :type payload: TokenPayload
        :param client_id: The expected Keycloak client identifier.
        :type client_id: str
        :returns: ``True`` if the token targets the client.
        :rtype: bool
        """
        audiences = cls._extract_audiences(payload)
        if client_id in audiences:
            return True

        azp = payload.get("azp")
        if isinstance(azp, str) and azp == client_id:
            return True

        resource_access = payload.get("resource_access")
        if isinstance(resource_access, dict) and client_id in resource_access:
            return True

        return False

    def _enforce_issuer_and_audience(self, payload: TokenPayload) -> None:
        """Validate that the token issuer and audience match expectations.

        :param payload: The decoded JWT claims.
        :type payload: TokenPayload
        :raises HTTPException: If the issuer or audience is invalid (HTTP 401).
        """
        issuer_raw = payload.get("iss")
        issuer = issuer_raw.rstrip("/") if isinstance(issuer_raw, str) else issuer_raw
        expected_issuer = self._expected_issuer()
        if issuer != expected_issuer:
            raise self._unauthorized(reason=f"issuer={issuer!r}, expected={expected_issuer!r}")

        if self._token_targets_client(payload, self._settings.keycloak_client_id):
            return

        aud = payload.get("aud")
        azp = payload.get("azp")
        raise self._unauthorized(
            reason=f"aud={aud!r}, azp={azp!r}, expected_client={self._settings.keycloak_client_id!r}",
        )


def get_token_service(settings: Settings = Depends(get_settings)) -> TokenService:
    """FastAPI dependency that provides a :class:`TokenService` instance.

    :param settings: Application settings (injected by FastAPI).
    :type settings: Settings
    :returns: A configured token service.
    :rtype: TokenService
    """
    return TokenService(settings=settings)


def decode_token(token: str, settings: Settings | None = None) -> TokenPayload:
    """Convenience function to decode a token outside of a request context.

    :param token: The raw JWT string.
    :type token: str
    :param settings: Optional settings override; defaults to :func:`get_settings`.
    :type settings: Settings | None
    :returns: The decoded token claims.
    :rtype: TokenPayload
    :raises HTTPException: If the token is invalid or expired.
    """
    return TokenService(settings=settings or get_settings()).decode(token)


def get_token_payload(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    token_service: TokenService = Depends(get_token_service),
) -> TokenPayload:
    """FastAPI dependency that extracts and validates the token payload from a request.

    :param request: The incoming FastAPI request.
    :type request: Request
    :param credentials: Optional Bearer credentials (injected by FastAPI).
    :type credentials: HTTPAuthorizationCredentials | None
    :param token_service: The token service instance (injected by FastAPI).
    :type token_service: TokenService
    :returns: The decoded and validated token claims.
    :rtype: TokenPayload
    :raises HTTPException: If authentication fails.
    """
    return token_service.from_request(request=request, credentials=credentials)
