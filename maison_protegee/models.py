"""Domain models reverse-engineered from the Android app."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AlarmMode(str, Enum):
    """Gateway alarm mode (GatewayMode.kt)."""

    TOTAL = "total"
    PARTIAL = "partial"
    NONE = ""


class AlarmStatus(str, Enum):
    """Gateway activation status (GatewayStatus.kt)."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class AlarmState(str, Enum):
    """High-level alarm state derived from mode."""

    TOTAL = "total_active"
    PARTIAL = "partial_active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"

    @classmethod
    def from_mode(cls, mode: str) -> AlarmState:
        if mode == AlarmMode.TOTAL.value:
            return cls.TOTAL
        if mode == AlarmMode.PARTIAL.value:
            return cls.PARTIAL
        if mode == AlarmMode.NONE.value:
            return cls.INACTIVE
        return cls.UNKNOWN


@dataclass(frozen=True)
class SessionInfo:
    access_token: str
    refresh_token: str
    username: str
    hashed_user_id: str
    contract_id: str
    gateway_id: str
    gateway_type: str


@dataclass(frozen=True)
class GatewayState:
    mode: str
    status: str
    delay: int
    alarm_state: AlarmState

    @classmethod
    def from_result(cls, mode: str, status: str, delay: int = 0) -> GatewayState:
        return cls(mode=mode, status=status, delay=delay, alarm_state=AlarmState.from_mode(mode))
