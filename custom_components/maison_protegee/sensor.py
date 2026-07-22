from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EquipmentDevice, EventRecord, MaisonProtegeeAPI
from .const import (
    CONF_ENABLE_DIAGNOSTICS,
    CONF_ENABLE_EQUIPMENT,
    CONF_ENABLE_EVENTS,
    DOMAIN,
)
from .coordinator import EquipmentCoordinator, EventsCoordinator, GatewayCoordinator
from .entity import MaisonProtegeeEntity, MaisonProtegeeEquipmentEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    api: MaisonProtegeeAPI = runtime["api"]

    entities: list[SensorEntity] = []

    if entry.data.get(CONF_ENABLE_DIAGNOSTICS, True):
        gateway_coordinator: GatewayCoordinator = runtime["gateway_coordinator"]
        entities.extend(
            [
                MaisonProtegeeContractSensor(gateway_coordinator, entry, api),
                MaisonProtegeeGatewaySensor(gateway_coordinator, entry, api),
            ]
        )

    equipment_coordinator: EquipmentCoordinator | None = runtime.get("equipment_coordinator")
    if equipment_coordinator is not None and entry.data.get(CONF_ENABLE_EQUIPMENT, True):
        for device in equipment_coordinator.data.devices:
            if device.battery is not None:
                entities.append(
                    MaisonProtegeeBatterySensor(
                        equipment_coordinator, entry, api, device
                    )
                )
            if device.signal_wifi is not None:
                entities.append(
                    MaisonProtegeeSignalWifiSensor(
                        equipment_coordinator, entry, api, device
                    )
                )
            if device.temperature is not None:
                entities.append(
                    MaisonProtegeeDeviceTemperatureSensor(
                        equipment_coordinator, entry, api, device
                    )
                )

    if entry.data.get(CONF_ENABLE_EVENTS, True):
        events_coordinator: EventsCoordinator = runtime["events_coordinator"]
        if events_coordinator.data:
            entities.append(
                MaisonProtegeeLatestEventSensor(events_coordinator, entry, api)
            )

    _LOGGER.info("Setting up %d sensor entities", len(entities))
    async_add_entities(entities)


class MaisonProtegeeContractSensor(MaisonProtegeeEntity, SensorEntity):
    _attr_translation_key = "contract_id"
    _attr_icon = "mdi:file-document-outline"

    def __init__(self, coordinator, entry, api) -> None:
        super().__init__(coordinator, entry, api)
        self._attr_unique_id = f"{entry.entry_id}_contract_id"

    @property
    def native_value(self) -> str | None:
        return self._api.contract_id


class MaisonProtegeeGatewaySensor(MaisonProtegeeEntity, SensorEntity):
    _attr_translation_key = "gateway_id"
    _attr_icon = "mdi:router-wireless"

    def __init__(self, coordinator, entry, api) -> None:
        super().__init__(coordinator, entry, api)
        self._attr_unique_id = f"{entry.entry_id}_gateway_id"

    @property
    def native_value(self) -> str | None:
        return self._api.gateway_id or "none"

    @property
    def extra_state_attributes(self) -> dict:
        return {"gateway_type": self._api.gateway_type}


class MaisonProtegeeBatterySensor(MaisonProtegeeEquipmentEntity, SensorEntity):
    _attr_translation_key = "battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator: EquipmentCoordinator,
        entry: ConfigEntry,
        api: MaisonProtegeeAPI,
        device: EquipmentDevice,
    ) -> None:
        super().__init__(coordinator, entry, api, device)
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id}_battery"

    @property
    def native_value(self) -> int | None:
        device = self._get_device()
        return device.battery if device else None


class MaisonProtegeeSignalWifiSensor(MaisonProtegeeEquipmentEntity, SensorEntity):
    _attr_translation_key = "signal_wifi"
    _attr_icon = "mdi:wifi"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: EquipmentCoordinator,
        entry: ConfigEntry,
        api: MaisonProtegeeAPI,
        device: EquipmentDevice,
    ) -> None:
        super().__init__(coordinator, entry, api, device)
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id}_signal_wifi"

    @property
    def native_value(self) -> int | None:
        device = self._get_device()
        return device.signal_wifi if device else None


class MaisonProtegeeDeviceTemperatureSensor(MaisonProtegeeEquipmentEntity, SensorEntity):
    _attr_translation_key = "device_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: EquipmentCoordinator,
        entry: ConfigEntry,
        api: MaisonProtegeeAPI,
        device: EquipmentDevice,
    ) -> None:
        super().__init__(coordinator, entry, api, device)
        self._attr_unique_id = f"{entry.entry_id}_{device.device_id}_temperature"

    @property
    def native_value(self) -> float | None:
        device = self._get_device()
        return device.temperature if device else None


class MaisonProtegeeLatestEventSensor(MaisonProtegeeEntity, SensorEntity):
    _attr_translation_key = "latest_event"
    _attr_icon = "mdi:history"

    def __init__(
        self,
        coordinator: EventsCoordinator,
        entry: ConfigEntry,
        api: MaisonProtegeeAPI,
    ) -> None:
        super().__init__(coordinator, entry, api)
        self._attr_unique_id = f"{entry.entry_id}_latest_event"

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data[0].message

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data:
            return {}
        latest: EventRecord = self.coordinator.data[0]
        return {
            "event_id": latest.event_id,
            "event_type": latest.event_type,
            "date_time": latest.date_time,
            "user": latest.user,
            "source": latest.source,
        }
