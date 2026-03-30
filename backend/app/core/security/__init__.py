"""
Security package.

Re-exports token decoding utilities and the :data:`TokenPayload` type alias
from the :mod:`app.core.security.token` module.
"""

from .token import TokenPayload, get_token_payload

__all__ = [
    "TokenPayload",
    "get_token_payload",
]
