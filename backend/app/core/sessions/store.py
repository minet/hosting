"""
Redis-backed authentication session store.

Provides helpers to persist OAuth2 authorisation state and user sessions
in Redis with automatic expiry.
"""

from __future__ import annotations

import json
from functools import lru_cache
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import Settings, get_settings


def _state_key(state: str, prefix: str) -> str:
    """Build the Redis key for an OAuth2 authorisation state entry.

    :param state: The unique state identifier.
    :type state: str
    :param prefix: The Redis key prefix for auth states.
    :type prefix: str
    :returns: The full Redis key.
    :rtype: str
    """
    return f"{prefix}{state}"


def _session_key(session_id: str, prefix: str) -> str:
    """Build the Redis key for a user session entry.

    :param session_id: The unique session identifier.
    :type session_id: str
    :param prefix: The Redis key prefix for sessions.
    :type prefix: str
    :returns: The full Redis key.
    :rtype: str
    """
    return f"{prefix}{session_id}"


def build_redis_client(settings: Settings) -> Redis:
    """Create a :class:`~redis.Redis` client from application settings.

    :param settings: Application settings containing the ``redis_url``.
    :type settings: Settings
    :returns: A configured Redis client with decoded string responses.
    :rtype: Redis
    """
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
    )


class SessionStore:
    """Redis-backed authentication state and session storage.

    Stores short-lived OAuth2 authorisation states and longer-lived user
    sessions, each keyed by a random hex identifier.
    """

    def __init__(self, redis_client: Redis, settings: Settings):
        """Initialise the session store.

        :param redis_client: A connected Redis client instance.
        :type redis_client: Redis
        :param settings: Application settings used for TTL and key prefix values.
        :type settings: Settings
        """
        self._redis = redis_client
        self._settings = settings

    def create_auth_state(self, redirect_target: str, code_verifier: str) -> str:
        """Create and persist an OAuth2 authorisation state.

        :param redirect_target: The URL to redirect to after authentication.
        :type redirect_target: str
        :param code_verifier: The PKCE code verifier for this flow.
        :type code_verifier: str
        :returns: The generated state identifier.
        :rtype: str
        :raises RuntimeError: If Redis is unavailable.
        """
        state = uuid4().hex
        payload = json.dumps({"redirect_target": redirect_target, "code_verifier": code_verifier})
        try:
            self._redis.setex(
                _state_key(state, self._settings.auth_state_key_prefix),
                self._settings.auth_state_ttl_seconds,
                payload,
            )
        except RedisError as exc:
            raise self._storage_unavailable(exc) from exc
        return state

    def consume_auth_state(self, state: str) -> tuple[str, str] | None:
        """Atomically retrieve and delete an OAuth2 authorisation state.

        :param state: The state identifier returned by :meth:`create_auth_state`.
        :type state: str
        :returns: A ``(redirect_target, code_verifier)`` tuple, or ``None``
            if the state does not exist or is malformed.
        :rtype: tuple[str, str] | None
        :raises RuntimeError: If Redis is unavailable.
        """
        key = _state_key(state, self._settings.auth_state_key_prefix)
        try:
            with self._redis.pipeline(transaction=True) as pipe:
                pipe.get(key)
                pipe.delete(key)
                raw_payload, _ = pipe.execute()
        except RedisError as exc:
            raise self._storage_unavailable(exc) from exc

        if not isinstance(raw_payload, str):
            return None

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            return None

        redirect_target = payload.get("redirect_target")
        code_verifier = payload.get("code_verifier")
        if not isinstance(redirect_target, str) or not isinstance(code_verifier, str):
            return None
        return redirect_target, code_verifier

    def update_session_tokens(self, session_id: str, *, access_token: str, refresh_token: str | None = None) -> None:
        """Update access (and optionally refresh) token for an existing session.

        :param session_id: The session identifier.
        :param access_token: The new access token.
        :param refresh_token: The new refresh token, if provided.
        :raises RuntimeError: If Redis is unavailable.
        """
        payload = self._session_payload(session_id)
        if payload is None:
            return
        payload["access_token"] = access_token
        if refresh_token is not None:
            payload["refresh_token"] = refresh_token
        try:
            key = _session_key(session_id, self._settings.auth_session_key_prefix)
            ttl = self._redis.ttl(key)
            self._redis.setex(key, ttl if ttl > 0 else self._settings.session_ttl_seconds, json.dumps(payload))
        except RedisError as exc:
            raise self._storage_unavailable(exc) from exc

    def get_refresh_token(self, session_id: str) -> str | None:
        """Retrieve the refresh token for a given session.

        :param session_id: The session identifier.
        :returns: The refresh token, or ``None`` if not found.
        :rtype: str | None
        :raises RuntimeError: If Redis is unavailable.
        """
        payload = self._session_payload(session_id)
        if payload is None:
            return None
        token = payload.get("refresh_token")
        if isinstance(token, str) and token:
            return token
        return None

    def create_session(self, *, access_token: str, id_token: str | None = None, refresh_token: str | None = None) -> str:
        """Create a new user session storing the provided tokens.

        :param access_token: The OAuth2 access token.
        :type access_token: str
        :param id_token: An optional OpenID Connect ID token.
        :type id_token: str | None
        :returns: The generated session identifier.
        :rtype: str
        :raises RuntimeError: If Redis is unavailable.
        """
        session_id = uuid4().hex
        payload = json.dumps({"access_token": access_token, "id_token": id_token, "refresh_token": refresh_token})
        try:
            self._redis.setex(
                _session_key(session_id, self._settings.auth_session_key_prefix),
                self._settings.session_ttl_seconds,
                payload,
            )
        except RedisError as exc:
            raise self._storage_unavailable(exc) from exc
        return session_id

    def get_access_token(self, session_id: str) -> str | None:
        """Retrieve the access token for a given session.

        :param session_id: The session identifier.
        :type session_id: str
        :returns: The access token, or ``None`` if the session does not exist
            or contains no valid access token.
        :rtype: str | None
        :raises RuntimeError: If Redis is unavailable.
        """
        payload = self._session_payload(session_id)
        if payload is None:
            return None
        token = payload.get("access_token")
        if isinstance(token, str) and token:
            return token
        return None

    def get_id_token(self, session_id: str) -> str | None:
        """Retrieve the ID token for a given session.

        :param session_id: The session identifier.
        :type session_id: str
        :returns: The ID token, or ``None`` if the session does not exist
            or contains no valid ID token.
        :rtype: str | None
        :raises RuntimeError: If Redis is unavailable.
        """
        payload = self._session_payload(session_id)
        if payload is None:
            return None
        token = payload.get("id_token")
        if isinstance(token, str) and token:
            return token
        return None

    def revoke_session(self, session_id: str) -> None:
        """Delete a user session from Redis.

        :param session_id: The session identifier to revoke.
        :type session_id: str
        :raises RuntimeError: If Redis is unavailable.
        """
        try:
            self._redis.delete(_session_key(session_id, self._settings.auth_session_key_prefix))
        except RedisError as exc:
            raise self._storage_unavailable(exc) from exc

    def _session_payload(self, session_id: str) -> dict[str, str | None] | None:
        """Retrieve and deserialise the JSON payload of a session.

        :param session_id: The session identifier.
        :type session_id: str
        :returns: The parsed payload dictionary, or ``None`` if not found or
            the stored value is not valid JSON.
        :rtype: dict[str, str | None] | None
        :raises RuntimeError: If Redis is unavailable.
        """
        try:
            raw_payload = self._redis.get(_session_key(session_id, self._settings.auth_session_key_prefix))
        except RedisError as exc:
            raise self._storage_unavailable(exc) from exc

        if not isinstance(raw_payload, str):
            return None

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None
        return payload

    @staticmethod
    def _storage_unavailable(_: Exception) -> RuntimeError:
        """Create a :class:`RuntimeError` indicating storage is unavailable.

        :param _: The original exception (not included in the message).
        :type _: Exception
        :returns: A ``RuntimeError`` with a descriptive message.
        :rtype: RuntimeError
        """
        return RuntimeError("Authentication session storage unavailable")


@lru_cache(maxsize=1)
def get_session_store() -> SessionStore:
    """Return a cached :class:`SessionStore` singleton backed by Redis.

    :returns: The shared session store instance.
    :rtype: SessionStore
    """
    settings = get_settings()
    return SessionStore(redis_client=build_redis_client(settings), settings=settings)
