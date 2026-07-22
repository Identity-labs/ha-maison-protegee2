"""Async adapter around the sync gRPC MaisonProtegeeClient."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .bootstrap import setup_import_path

setup_import_path()

from maison_protegee.client import MaisonProtegeeClient  # noqa: E402
from maison_protegee.exceptions import ApiError, AuthenticationError  # noqa: E402
from maison_protegee.models import AlarmStatus, GatewayState, SessionInfo  # noqa: E402

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class EquipmentSensor:
    """Temperature reading for a room/zone."""

    unique_id: str
    name: str
    value: float
    location: str


@dataclass(slots=True)
class EquipmentDevice:
    """Single piece of equipment from equipmentQueryList."""

    device_id: str
    name: str
    model: str
    location: str
    location_detail: str
    connection: str
    scene: str
    status_mode: str
    battery: int | None
    signal_wifi: int | None
    status: str | None
    temperature: float | None
    privacy_mode: str | None


@dataclass(slots=True)
class EquipmentSnapshot:
    """Parsed equipmentQueryList response."""

    devices: list[EquipmentDevice]
    zone_temperatures: list[EquipmentSensor]


@dataclass(slots=True)
class EventRecord:
    """Alarm system event."""

    event_id: str
    event_type: str
    date_time: str
    user: str
    source: str
    message: str


class MaisonProtegeeAPI:
    """Home Assistant async facade for MaisonProtegeeClient."""

    def __init__(self, username: str, password: str, timeout: int = 60) -> None:
        self._client = MaisonProtegeeClient(username, password, timeout=float(timeout))
        self._authenticated = False
        self._last_successful_auth_time: datetime | None = None
        self._lock = asyncio.Lock()
        self._session: SessionInfo | None = None

    @property
    def session(self) -> SessionInfo | None:
        return self._session

    @property
    def has_gateway(self) -> bool:
        return bool(self._client._gateway_id)

    @property
    def contract_id(self) -> str | None:
        return self._client._contract_id

    @property
    def gateway_id(self) -> str | None:
        return self._client._gateway_id

    @property
    def gateway_type(self) -> str | None:
        return self._client._gateway_type

    @property
    def hub_identifier(self) -> str:
        return self.gateway_id or self.contract_id or ""

    def get_last_successful_auth_time(self) -> datetime | None:
        return self._last_successful_auth_time

    async def _run(self, func, *args, **kwargs):
        async with self._lock:
            return await asyncio.to_thread(func, *args, **kwargs)

    async def async_authenticate(self) -> bool:
        try:
            self._session = await self._run(self._client.login)
            self._authenticated = True
            self._last_successful_auth_time = datetime.now()
            _LOGGER.info(
                "Authenticated as %s (contract=%s, gateway=%s)",
                self._session.username,
                self._session.contract_id or "none",
                self._session.gateway_id or "none",
            )
            return True
        except AuthenticationError as err:
            _LOGGER.error("Authentication failed: %s", err)
        except ApiError as err:
            _LOGGER.error("API error during login: %s", err)
        except Exception:
            _LOGGER.exception("Unexpected error during authentication")
        self._authenticated = False
        self._session = None
        return False

    async def async_ensure_authenticated(self) -> bool:
        if self._authenticated:
            try:
                await self._run(self._client.ensure_token_valid)
                return True
            except (AuthenticationError, ApiError):
                self._authenticated = False
        return await self.async_authenticate()

    async def async_get_gateway_state(self) -> GatewayState | None:
        if not await self.async_ensure_authenticated():
            return None
        if not self.has_gateway:
            return None
        try:
            return await self._run(self._client.get_gateway_status)
        except ApiError as err:
            _LOGGER.warning("Failed to get gateway status: %s", err)
            return None
        except Exception:
            _LOGGER.exception("Unexpected error getting gateway status")
            return None

    async def async_arm_total(self) -> GatewayState | None:
        return await self._gateway_command(self._client.arm_total)

    async def async_arm_partial(self) -> GatewayState | None:
        return await self._gateway_command(self._client.arm_partial)

    async def async_disarm(self) -> GatewayState | None:
        return await self._gateway_command(self._client.disarm)

    async def _gateway_command(self, func) -> GatewayState | None:
        if not await self.async_ensure_authenticated():
            return None
        if not self.has_gateway:
            _LOGGER.error("Gateway command refused — no gateway on contract")
            return None
        try:
            return await self._run(func)
        except ApiError as err:
            _LOGGER.error("Gateway command failed: %s", err)
            return None
        except Exception:
            _LOGGER.exception("Unexpected error during gateway command")
            return None

    async def async_get_equipment(self) -> EquipmentSnapshot:
        if not await self.async_ensure_authenticated():
            return EquipmentSnapshot(devices=[], zone_temperatures=[])

        try:
            response = await self._run(self._client.list_equipment)
            return self._parse_equipment_response(response)
        except ApiError as err:
            _LOGGER.warning("Failed to get equipment: %s", err)
            return EquipmentSnapshot(devices=[], zone_temperatures=[])
        except Exception:
            _LOGGER.exception("Unexpected error getting equipment")
            return EquipmentSnapshot(devices=[], zone_temperatures=[])

    async def async_get_temperatures(self) -> list[EquipmentSensor]:
        """Zone-level temperature sensors (subset of equipment list)."""
        return (await self.async_get_equipment()).zone_temperatures

    async def async_get_events(self, limit: int = 20) -> list[EventRecord]:
        if not await self.async_ensure_authenticated():
            return []
        try:
            response = await self._run(self._client.list_events, limit)
            events: list[EventRecord] = []
            for item in response.eventList:
                message_parts = [p for p in (item.type, item.user, item.source) if p]
                events.append(
                    EventRecord(
                        event_id=item.eventId,
                        event_type=self._guess_event_type(item.type),
                        date_time=item.dateTime or "",
                        user=item.user or "",
                        source=item.source or "",
                        message=" — ".join(message_parts) if message_parts else item.eventId,
                    )
                )
            return events
        except ApiError as err:
            _LOGGER.warning("Failed to get events: %s", err)
            return []
        except Exception:
            _LOGGER.exception("Unexpected error getting events")
            return []

    async def async_logout(self, force: bool = False) -> None:
        if not self._authenticated and not force:
            return
        try:
            await self._run(self._client.close)
        except Exception:
            _LOGGER.debug("Error closing gRPC client", exc_info=True)
        finally:
            self._authenticated = False
            self._session = None

    def _parse_equipment_response(self, response: Any) -> EquipmentSnapshot:
        devices: list[EquipmentDevice] = []
        zone_temperatures: list[EquipmentSensor] = []

        for group in response.equipmentListResult:
            location = group.location.strip() or "Unknown"
            temp_raw = group.temperature.strip()
            if temp_raw:
                temp_value = self._parse_temperature(temp_raw)
                if temp_value is not None:
                    zone_temperatures.append(
                        EquipmentSensor(
                            unique_id=self._slugify(location),
                            name=location,
                            value=temp_value,
                            location=location,
                        )
                    )

            for eq in group.equipmenList:
                device_id = eq.deviceId.strip()
                if not device_id:
                    continue

                attrs = eq.attributes if eq.HasField("attributes") else None
                params = eq.parameters if eq.HasField("parameters") else None

                battery: int | None = None
                signal_wifi: int | None = None
                status: str | None = None
                device_temp: float | None = None
                privacy_mode: str | None = None

                if attrs is not None:
                    # Orange reports battery on a 0–10 scale (10 = 100%).
                    if attrs.battery > 0:
                        battery = min(int(attrs.battery) * 10, 100)
                    if attrs.signalWifi > 0:
                        signal_wifi = attrs.signalWifi
                    if attrs.status.strip():
                        status = attrs.status.strip()
                    temp_raw = attrs.temperature.strip()
                    if temp_raw:
                        device_temp = self._parse_temperature(temp_raw)
                    if attrs.privacyMode.strip():
                        privacy_mode = attrs.privacyMode.strip()

                devices.append(
                    EquipmentDevice(
                        device_id=device_id,
                        name=eq.intitule.strip() or device_id,
                        model=eq.model.strip(),
                        location=location,
                        location_detail=eq.locationDetail.strip(),
                        connection=eq.connection.strip(),
                        scene=eq.scene.strip(),
                        status_mode=params.statusMode.strip() if params else "",
                        battery=battery,
                        signal_wifi=signal_wifi,
                        status=status,
                        temperature=device_temp,
                        privacy_mode=privacy_mode,
                    )
                )

        return EquipmentSnapshot(
            devices=devices,
            zone_temperatures=zone_temperatures,
        )

    @staticmethod
    def map_gateway_to_ha_state(state: GatewayState):
        """Map gRPC gateway state to HA AlarmControlPanelState.

        ``delay`` is the configured exit/entry temporisation (seconds), not a
        live countdown — do not treat delay>0 as PENDING or the panel stays
        stuck on "En attente" while already armed.
        """
        from homeassistant.components.alarm_control_panel import AlarmControlPanelState

        if state.status == AlarmStatus.ACTIVE.value:
            if state.mode == "total":
                return AlarmControlPanelState.ARMED_AWAY
            if state.mode == "partial":
                return AlarmControlPanelState.ARMED_HOME
            # Active without a known mode — still armed.
            return AlarmControlPanelState.ARMED_AWAY
        return AlarmControlPanelState.DISARMED

    @staticmethod
    def _parse_temperature(value: str) -> float | None:
        cleaned = value.replace("°C", "").replace("°", "").strip().replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
            if match:
                try:
                    return float(match.group(0))
                except ValueError:
                    return None
        return None

    @staticmethod
    def _slugify(value: str) -> str:
        slug = value.lower()
        for src, dst in (("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"), ("ù", "u")):
            slug = slug.replace(src, dst)
        slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
        return slug or "room"

    @staticmethod
    def _guess_event_type(event_type: str) -> str:
        lowered = (event_type or "").lower()
        if "arm" in lowered or "activ" in lowered:
            return "arm"
        if "disarm" in lowered or "désactiv" in lowered or "desactiv" in lowered:
            return "disarm"
        return "unknown"
