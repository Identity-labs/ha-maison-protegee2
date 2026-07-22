from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import Event, HomeAssistant, callback

from .api import MaisonProtegeeAPI
from .bootstrap import setup_import_path
from .const import DOMAIN
from .coordinator import EquipmentCoordinator, EventsCoordinator, GatewayCoordinator

setup_import_path()

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    domain_data = hass.data[DOMAIN]
    if entry.entry_id in domain_data:
        _LOGGER.warning("Entry %s already set up, cleaning up first", entry.entry_id)
        await _async_cleanup_entry(domain_data.pop(entry.entry_id))

    if f"{DOMAIN}_shutdown_listener" not in hass.data:

        @callback
        async def async_shutdown_listener(_event: Event) -> None:
            for entry_data in list(hass.data.get(DOMAIN, {}).values()):
                if isinstance(entry_data, dict) and "api" in entry_data:
                    await entry_data["api"].async_logout(force=True)

        hass.bus.async_listen_once("homeassistant_stop", async_shutdown_listener)
        hass.data[f"{DOMAIN}_shutdown_listener"] = True

    api = MaisonProtegeeAPI(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    if not await api.async_authenticate():
        await api.async_logout(force=True)
        return False

    gateway_coordinator = GatewayCoordinator(hass, api, entry)
    equipment_coordinator = EquipmentCoordinator(hass, api, entry)
    events_coordinator = EventsCoordinator(hass, api, entry)

    await gateway_coordinator.async_config_entry_first_refresh()
    await equipment_coordinator.async_config_entry_first_refresh()
    await events_coordinator.async_config_entry_first_refresh()

    domain_data[entry.entry_id] = {
        "api": api,
        "gateway_coordinator": gateway_coordinator,
        "equipment_coordinator": equipment_coordinator,
        "events_coordinator": events_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and entry.entry_id in hass.data.get(DOMAIN, {}):
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        await _async_cleanup_entry(entry_data)
    return unload_ok


async def _async_cleanup_entry(entry_data: dict) -> None:
    if "api" in entry_data:
        await entry_data["api"].async_logout(force=True)


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
