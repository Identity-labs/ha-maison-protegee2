"""Shared data update coordinators."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EquipmentSnapshot, EventRecord, MaisonProtegeeAPI
from .const import (
    CONF_SCAN_INTERVAL_ALARM,
    CONF_SCAN_INTERVAL_EVENTS,
    CONF_SCAN_INTERVAL_TEMPERATURES,
    DEFAULT_SCAN_INTERVAL_ALARM,
    DEFAULT_SCAN_INTERVAL_EVENTS,
    DEFAULT_SCAN_INTERVAL_TEMPERATURES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _interval(entry: ConfigEntry, key: str, default: int) -> timedelta:
    return timedelta(seconds=int(entry.data.get(key, default)))


class GatewayCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls gateway/alarm state."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: MaisonProtegeeAPI,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_gateway_{entry.entry_id}",
            update_interval=_interval(
                entry, CONF_SCAN_INTERVAL_ALARM, DEFAULT_SCAN_INTERVAL_ALARM
            ),
        )
        self.api = api
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            state = await self.api.async_get_gateway_state()
            if state is None and self.api.has_gateway:
                raise UpdateFailed("Gateway status unavailable")
            return {
                "gateway_state": state,
                "available": state is not None,
            }
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout: {err}") from err


class EquipmentCoordinator(DataUpdateCoordinator[EquipmentSnapshot]):
    """Polls equipment list (zone temps + per-device attributes)."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: MaisonProtegeeAPI,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_equipment_{entry.entry_id}",
            update_interval=_interval(
                entry,
                CONF_SCAN_INTERVAL_TEMPERATURES,
                DEFAULT_SCAN_INTERVAL_TEMPERATURES,
            ),
        )
        self.api = api
        self.entry = entry

    async def _async_update_data(self) -> EquipmentSnapshot:
        try:
            return await self.api.async_get_equipment()
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout: {err}") from err


class EventsCoordinator(DataUpdateCoordinator[list[EventRecord]]):
    """Polls event log and fires bus events for new entries."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: MaisonProtegeeAPI,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_events_{entry.entry_id}",
            update_interval=_interval(
                entry, CONF_SCAN_INTERVAL_EVENTS, DEFAULT_SCAN_INTERVAL_EVENTS
            ),
        )
        self.api = api
        self.entry = entry
        self._last_processed_event_id: str | None = None

    async def _async_update_data(self) -> list[EventRecord]:
        try:
            events = await self.api.async_get_events()
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout: {err}") from err

        if not events:
            return []

        if self._last_processed_event_id is None:
            self._last_processed_event_id = events[0].event_id
            self._fire_new_events(events)
            return events

        new_events: list[EventRecord] = []
        for event in events:
            if event.event_id == self._last_processed_event_id:
                break
            new_events.append(event)

        if new_events:
            self._last_processed_event_id = new_events[0].event_id
            self._fire_new_events(list(reversed(new_events)))

        return events

    def _fire_new_events(self, events: list[EventRecord]) -> None:
        for event in events:
            self.hass.bus.async_fire(
                f"{DOMAIN}_event",
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "date_time": event.date_time,
                    "user": event.user,
                    "source": event.source,
                    "message": event.message,
                },
            )
