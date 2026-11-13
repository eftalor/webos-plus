"""Picture sliders for LG webOS TV Plus."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .coordinator import WebOsPlusConfigEntry
from .entity import WebOsPlusOnEntity, cmd

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PictureSlider:
    """A picture number and the system-setting key it writes."""

    description: NumberEntityDescription
    setting: str
    minimum: float = 0
    maximum: float = 100
    unit: str | None = PERCENTAGE


def _slider(
    key: str,
    setting: str | None = None,
    *,
    icon: str | None = None,
    minimum: float = 0,
    maximum: float = 100,
    unit: str | None = PERCENTAGE,
) -> PictureSlider:
    return PictureSlider(
        description=NumberEntityDescription(
            key=key,
            translation_key=key,
            icon=icon,
            entity_category=EntityCategory.CONFIG,
        ),
        setting=setting or key,
        minimum=minimum,
        maximum=maximum,
        unit=unit,
    )


NUMBERS = (
    _slider("backlight", icon="mdi:brightness-6"),
    _slider("brightness"),
    _slider("contrast"),
    _slider("color"),
    _slider("sharpness", icon="mdi:details", maximum=50, unit=None),
    _slider(
        "color_temperature",
        "colorTemperature",
        icon="mdi:thermometer",
        minimum=-50,
        maximum=50,
        unit=None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebOsPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up numbers."""
    async_add_entities(PictureNumber(entry, slider) for slider in NUMBERS)


class PictureNumber(WebOsPlusOnEntity, RestoreEntity, NumberEntity):
    """A picture setting. Live when the TV reports it, otherwise the last value set."""

    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, entry: WebOsPlusConfigEntry, slider: PictureSlider) -> None:
        """Initialize."""
        super().__init__(entry, slider.description.key)
        self.entity_description = slider.description
        self._setting = slider.setting
        self._attr_native_min_value = slider.minimum
        self._attr_native_max_value = slider.maximum
        self._attr_native_unit_of_measurement = slider.unit
        self._restored: float | None = None

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self._restored = _parse_number(last.state)

    @property
    @override
    def assumed_state(self) -> bool:
        """True until a subscription confirms the value."""
        return self._setting not in self.coordinator.live_settings

    @property
    @override
    def native_value(self) -> float | None:
        parsed = _parse_number(self.coordinator.settings.get(self._setting))
        if parsed is None:
            return self._restored
        return parsed

    @cmd
    @override
    async def async_set_native_value(self, value: float) -> None:
        whole = int(value)
        await self.coordinator.async_set_setting("picture", self._setting, whole)
        self.coordinator.settings[self._setting] = whole
        self._restored = float(whole)
        self.async_write_ha_state()


def _parse_number(value: object) -> float | None:
    """Return a number from a TV setting or a restored state."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
