"""
Access-token decoding and validation module.

Provides :class:`TokenService` which validates Keycloak-issued JWTs,
and FastAPI dependency helpers for extracting the token payload from
incoming requests.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwcrypto.common import JWException
from keycloak import KeycloakOpenID
from keycloak.exceptions import KeycloakError

import logging

from app.core.config import Settings, get_settings
from app.core.sessions import get_access_token

logger = logging.getLogger(__name__)

TokenPayload = dict[str, Any]
http_bearer = HTTPBearer(auto_error=False)


class TokenService:
    """Decode and validate access tokens from a Bearer header or cookie."""

    def __init__(self, *, settings: Settings):
        self._settings = settings
        self._keycloak = KeycloakOpenID(
            server_url=settings.keycloak_server_url,
            realm_name=settings.keycloak_realm,
            client_id=settings.keycloak_client_id,
            client_secret_key=settings.keycloak_client_secret,
            verify=settings.keycloak_verify_tls,
        )

    def decode(self, token: str) -> TokenPayload:
        """Decode and validate a JWT access token."""
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
        2. An access token stored in an httponly cookie.
        """
        if credentials is not None and credentials.scheme.lower() == "bearer":
            return self.decode(credentials.credentials)

        access_token = get_access_token(request)
        if access_token:
            logger.info("from_request: cookie found (%d chars)", len(access_token))
            return self.decode(access_token)

        cookie_names = list(request.cookies.keys())
        logger.warning("from_request: no access token. cookies present: %s", cookie_names)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token or access token cookie",
        )

    def _unauthorized(self, *, reason: str | None = None) -> HTTPException:
        detail = "Invalid or expired token"
        if self._settings.app_debug and reason:
            detail = f"{detail} ({reason})"
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

    def _expected_issuer(self) -> str:
        return self._settings.keycloak_issuer.rstrip("/")

    @staticmethod
    def _extract_audiences(payload: TokenPayload) -> set[str]:
        aud_claim = payload.get("aud")
        if isinstance(aud_claim, str):
            return {aud_claim}
        if isinstance(aud_claim, list):
            return {str(item) for item in aud_claim}
        return set()

    @classmethod
    def _token_targets_client(cls, payload: TokenPayload, client_id: str) -> bool:
        audiences = cls._extract_audiences(payload)
        if client_id in audiences:
            return True
        azp = payload.get("azp")
        if isinstance(azp, str) and azp == client_id:
            return True
        resource_access = payload.get("resource_access")
        return isinstance(resource_access, dict) and client_id in resource_access

    def _enforce_issuer_and_audience(self, payload: TokenPayload) -> None:
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
    return TokenService(settings=settings)


def decode_token(token: str, settings: Settings | None = None) -> TokenPayload:
    return TokenService(settings=settings or get_settings()).decode(token)


def get_token_payload(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
    token_service: TokenService = Depends(get_token_service),
) -> TokenPayload:
    return token_service.from_request(request=request, credentials=credentials)
