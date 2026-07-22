from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import MaisonProtegeeAPI
from .const import CONF_ENABLE_ALARM_PANEL, DOMAIN
from .coordinator import GatewayCoordinator
from .entity import MaisonProtegeeEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if not entry.data.get(CONF_ENABLE_ALARM_PANEL, True):
        return

    runtime = hass.data[DOMAIN][entry.entry_id]
    api: MaisonProtegeeAPI = runtime["api"]
    coordinator: GatewayCoordinator = runtime["gateway_coordinator"]

    if not api.has_gateway:
        _LOGGER.warning(
            "Alarm panel not created — contract has no gateway (installation pending?)"
        )
        return

    async_add_entities([MaisonProtegeeAlarmPanel(coordinator, entry, api)])


class MaisonProtegeeAlarmPanel(MaisonProtegeeEntity, AlarmControlPanelEntity):
    """Maison Protégée alarm with total (away) and partial (home) modes."""

    _attr_code_arm_required = False
    _attr_code_format = CodeFormat.NUMBER
    # DISARM is always available; it is not an AlarmControlPanelEntityFeature.
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )

    def __init__(
        self,
        coordinator: GatewayCoordinator,
        entry: ConfigEntry,
        api: MaisonProtegeeAPI,
    ) -> None:
        super().__init__(coordinator, entry, api)
        self._attr_unique_id = f"{entry.entry_id}_alarm"
        self._attr_name = None
        self._attr_translation_key = "alarm_panel"

    @property
    def available(self) -> bool:
        data = self.coordinator.data or {}
        return bool(data.get("available")) and data.get("gateway_state") is not None

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        state = (self.coordinator.data or {}).get("gateway_state")
        if state is None:
            return None
        return MaisonProtegeeAPI.map_gateway_to_ha_state(state)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        if await self._api.async_disarm():
            await self.coordinator.async_request_refresh()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        if await self._api.async_arm_partial():
            await self.coordinator.async_request_refresh()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        if await self._api.async_arm_total():
            await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.coordinator.data.get("gateway_state")
        if state is None:
            return {}
        return {
            "mode": state.mode,
            "status": state.status,
            "delay": state.delay,
            "alarm_state": state.alarm_state.value,
            "gateway_id": self._api.gateway_id,
            "contract_id": self._api.contract_id,
        }
