"""Buttons for LG webOS TV Plus."""

from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LUNA_SHOW_INPUT_PICKER
from .coordinator import WebOsPlusConfigEntry, async_luna_request
from .entity import WebOsPlusOnEntity, cmd

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebOsPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    async_add_entities([InputPickerButton(entry)])


class InputPickerButton(WebOsPlusOnEntity, ButtonEntity):
    """Open the TV's input picker on screen."""

    _attr_translation_key = "input_picker"

    def __init__(self, entry: WebOsPlusConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "input_picker")

    @cmd
    @override
    async def async_press(self) -> None:
        await async_luna_request(self._client, LUNA_SHOW_INPUT_PICKER, {})
