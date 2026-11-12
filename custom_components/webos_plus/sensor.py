"""Sensors for LG webOS TV Plus."""

from typing import override

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WebOsPlusConfigEntry
from .entity import WebOsPlusEntity

PARALLEL_UPDATES = 0

POWER_STATES = ["on", "screen_off", "standby", "off"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebOsPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    async_add_entities([PowerStateSensor(entry), CurrentAppSensor(entry)])


class PowerStateSensor(WebOsPlusEntity, SensorEntity):
    """on / screen_off / standby / off."""

    _attr_translation_key = "power_state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = POWER_STATES

    def __init__(self, entry: WebOsPlusConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "power_state")

    @property
    @override
    def native_value(self) -> str:
        return self.coordinator.power_state


class CurrentAppSensor(WebOsPlusEntity, SensorEntity):
    """The app or input in the foreground, with its icon."""

    _attr_translation_key = "current_app"

    def __init__(self, entry: WebOsPlusConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "current_app")

    @property
    @override
    def native_value(self) -> str | None:
        if not self.coordinator.is_on:
            return None
        tv = self._client.tv_state
        app_id = tv.current_app_id or ""
        if app := tv.apps.get(app_id):
            return app["title"]
        for inp in tv.inputs.values():
            if inp["appId"] == app_id:
                return inp["label"]
        return app_id or None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str | None]:
        return {"app_id": self._client.tv_state.current_app_id if self.coordinator.is_on else None}
