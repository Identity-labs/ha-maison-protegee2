"""Base entity with device registry support."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import EquipmentDevice, MaisonProtegeeAPI
from .const import DOMAIN, MANUFACTURER


def format_equipment_name(device: EquipmentDevice) -> str:
    """Build a unique, human-readable device name.

    Many Orange devices share the same intitulé (e.g. several
    "Détecteur de mouvement"); disambiguate with location / detail.
    """
    base = (device.name or "").strip() or device.device_id
    location = (device.location or "").strip()
    detail = (device.location_detail or "").strip()

    if location and detail:
        return f"{base} ({location} — {detail})"
    if detail:
        return f"{base} ({detail})"
    if location:
        return f"{base} ({location})"
    return base


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

    # The control panel is listed in equipment with the same deviceId as the
    # gateway — attach its entities to the hub instead of colliding.
    if hub_id and device.device_id == hub_id:
        return DeviceInfo(identifiers={(DOMAIN, hub_id)})

    return DeviceInfo(
        identifiers={(DOMAIN, device.device_id)},
        name=format_equipment_name(device),
        manufacturer=MANUFACTURER,
        model=device.model or "Equipment",
        via_device=(DOMAIN, hub_id) if hub_id else None,
        suggested_area=device.location or None,
        serial_number=device.device_id,
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
