from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EquipmentDevice, MaisonProtegeeAPI
from .const import CONF_ENABLE_EQUIPMENT, DOMAIN
from .coordinator import EquipmentCoordinator
from .entity import MaisonProtegeeEquipmentEntity

_LOGGER = logging.getLogger(__name__)

_ONLINE_VALUES = frozenset({"online"})
_ACTIVE_VALUES = frozenset({"active"})
_BOOL_MODE_VALUES = frozenset({"true", "false", "1", "0"})


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if not entry.data.get(CONF_ENABLE_EQUIPMENT, True):
        return

    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator: EquipmentCoordinator = runtime["equipment_coordinator"]
    api: MaisonProtegeeAPI = runtime["api"]

    entities: list[BinarySensorEntity] = []
    for device in coordinator.data.devices:
        if device.connection:
            entities.append(
                MaisonProtegeeConnectionBinarySensor(coordinator, entry, api, device)
            )
        if device.status and device.status.lower() in _ACTIVE_VALUES | {"inactive"}:
            entities.append(
                MaisonProtegeeStatusBinarySensor(coordinator, entry, api, device)
            )
        # statusMode true/false is a contact state on MAG-* sensors; on PIR it
        # is not a reliable opening signal, so only expose it for MAG models.
        if (
            device.status_mode
            and device.status_mode.strip().lower() in _BOOL_MODE_VALUES
            and "MAG" in (device.model or "").upper()
        ):
            entities.append(
                MaisonProtegeeStatusModeBinarySensor(coordinator, entry, api, device)
            )

    _LOGGER.info("Setting up %d binary_sensor entities", len(entities))
    async_add_entities(entities)


class MaisonProtegeeConnectionBinarySensor(MaisonProtegeeEquipmentEntity, BinarySensorEntity):
    _attr_translation_key = "connection"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: EquipmentCoordinator,
        entry: ConfigEntry,
        api: MaisonProtegeeAPI,
        device: EquipmentDevice,
    ) -> None:
        super().__init__(coordinator, entry, api, device)
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id}_connection"

    @property
    def is_on(self) -> bool | None:
        device = self._get_device()
        if device is None or not device.connection:
            return None
        return device.connection.strip().lower() in _ONLINE_VALUES


class MaisonProtegeeStatusBinarySensor(MaisonProtegeeEquipmentEntity, BinarySensorEntity):
    _attr_translation_key = "status"

    def __init__(
        self,
        coordinator: EquipmentCoordinator,
        entry: ConfigEntry,
        api: MaisonProtegeeAPI,
        device: EquipmentDevice,
    ) -> None:
        super().__init__(coordinator, entry, api, device)
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id}_status"

    @property
    def is_on(self) -> bool | None:
        device = self._get_device()
        if device is None or not device.status:
            return None
        status = device.status.strip().lower()
        if status in _ACTIVE_VALUES:
            return True
        if status == "inactive":
            return False
        return None

    @property
    def extra_state_attributes(self) -> dict:
        device = self._get_device()
        if device is None:
            return {}
        attrs = {"raw_status": device.status}
        if device.status_mode:
            attrs["status_mode"] = device.status_mode
        if device.privacy_mode:
            attrs["privacy_mode"] = device.privacy_mode
        return attrs


class MaisonProtegeeStatusModeBinarySensor(MaisonProtegeeEquipmentEntity, BinarySensorEntity):
    """Contact / zone state from equipment statusMode (true/false)."""

    _attr_translation_key = "status_mode"
    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(
        self,
        coordinator: EquipmentCoordinator,
        entry: ConfigEntry,
        api: MaisonProtegeeAPI,
        device: EquipmentDevice,
    ) -> None:
        super().__init__(coordinator, entry, api, device)
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id}_status_mode"

    @property
    def is_on(self) -> bool | None:
        device = self._get_device()
        if device is None or not device.status_mode:
            return None
        value = device.status_mode.strip().lower()
        if value in {"true", "1"}:
            return True
        if value in {"false", "0"}:
            return False
        return None
