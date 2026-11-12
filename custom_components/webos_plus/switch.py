"""Screen switch for LG webOS TV Plus (sound keeps playing with the screen off)."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WebOsPlusConfigEntry
from .entity import WebOsPlusOnEntity, cmd

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebOsPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch."""
    async_add_entities([ScreenSwitch(entry)])


class ScreenSwitch(WebOsPlusOnEntity, SwitchEntity):
    """Turn the screen off while the TV stays on (e.g. for music)."""

    _attr_translation_key = "screen"

    def __init__(self, entry: WebOsPlusConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "screen")

    @property
    @override
    def is_on(self) -> bool:
        return self._client.tv_state.is_screen_on

    @cmd
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._client.set_screen_state(True)

    @cmd
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._client.set_screen_state(False)
