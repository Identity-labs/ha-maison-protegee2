"""Orange Maison Protégée gRPC client (reverse-engineered from APK v5.9)."""

from maison_protegee.client import MaisonProtegeeClient
from maison_protegee.exceptions import ApiError, AuthenticationError, MaisonProtegeeError
from maison_protegee.models import AlarmMode, AlarmState, AlarmStatus, GatewayState, SessionInfo

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
