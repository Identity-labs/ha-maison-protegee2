"""Base entity with device registry support."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import EquipmentDevice, MaisonProtegeeAPI
from .const import DOMAIN, MANUFACTURER


def build_device_info(api: MaisonProtegeeAPI, entry: ConfigEntry) -> DeviceInfo:
    """Build the hub device entry for the contract/gateway."""
    gateway_id = api.gateway_id
    contract_id = api.contract_id or entry.entry_id
    identifier = api.hub_identifier or contract_id
    name_suffix = api.gateway_type or "Maison Protégée"

    return DeviceInfo(
        identifiers={(DOMAIN, identifier)},
        name=f"Maison Protégée {name_suffix}",
        manufacturer=MANUFACTURER,
        model=api.gateway_type or "Contract",
        sw_version="5.9",
        configuration_url="https://maison-protegee.orange.fr",
        suggested_area="Home",
        serial_number=gateway_id,
    )


def build_equipment_device_info(
    api: MaisonProtegeeAPI,
    device: EquipmentDevice,
) -> DeviceInfo:
    """Build a device registry entry for a single piece of equipment."""
    hub_id = api.hub_identifier
    suggested_area = device.location_detail or device.location or None

    return DeviceInfo(
        identifiers={(DOMAIN, device.device_id)},
        name=device.name,
        manufacturer=MANUFACTURER,
        model=device.model or "Equipment",
        via_device={(DOMAIN, hub_id)} if hub_id else None,
        suggested_area=suggested_area,
    )


class MaisonProtegeeEntity(CoordinatorEntity):
    """Base class for Maison Protégée hub entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry, api: MaisonProtegeeAPI) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._api = api
        self._attr_device_info = build_device_info(api, entry)


class MaisonProtegeeEquipmentEntity(CoordinatorEntity):
    """Base class for per-equipment entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        api: MaisonProtegeeAPI,
        device: EquipmentDevice,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._api = api
        self._device_id = device.device_id
        self._attr_device_info = build_equipment_device_info(api, device)

    def _get_device(self) -> EquipmentDevice | None:
        for device in self.coordinator.data.devices:
            if device.device_id == self._device_id:
                return device
        return None
