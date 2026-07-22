"""Orange Maison Protégée gRPC client (reverse-engineered from APK v5.9)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from maison_protegee.exceptions import ApiError, AuthenticationError, MaisonProtegeeError
from maison_protegee.models import AlarmMode, AlarmState, AlarmStatus, GatewayState, SessionInfo

if TYPE_CHECKING:
    from maison_protegee.client import MaisonProtegeeClient

__all__ = [
    "MaisonProtegeeClient",
    "MaisonProtegeeError",
    "AuthenticationError",
    "ApiError",
    "AlarmMode",
    "AlarmStatus",
    "AlarmState",
    "GatewayState",
    "SessionInfo",
]


def __getattr__(name: str):
    if name == "MaisonProtegeeClient":
        from maison_protegee.client import MaisonProtegeeClient as _Client

        return _Client
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
