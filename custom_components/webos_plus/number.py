"""Picture sliders for LG webOS TV Plus."""

from typing import override

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WebOsPlusConfigEntry
from .entity import WebOsPlusOnEntity, cmd

PARALLEL_UPDATES = 1

NUMBERS = (
    NumberEntityDescription(
        key="backlight", translation_key="backlight", icon="mdi:brightness-6",
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key="brightness", translation_key="brightness", entity_category=EntityCategory.CONFIG
    ),
    NumberEntityDescription(
        key="contrast", translation_key="contrast", entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    NumberEntityDescription(
        key="color", translation_key="color", entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebOsPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up numbers."""
    async_add_entities(PictureNumber(entry, d) for d in NUMBERS)


class PictureNumber(WebOsPlusOnEntity, NumberEntity):
    """A 0-100 picture setting, kept in sync by the TV's push updates."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, entry: WebOsPlusConfigEntry, description: NumberEntityDescription) -> None:
        """Initialize."""
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> float | None:
        value = self.coordinator.settings.get(self.entity_description.key)
        try:
            return float(value) if value is not None else None
        except ValueError:
            return None

    @cmd
    @override
    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_setting("picture", self.entity_description.key, int(value))
