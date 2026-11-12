"""Buttons for LG webOS TV Plus."""

from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .agent import AgentError
from .const import LOGGER, LUNA_SHOW_INPUT_PICKER
from .coordinator import WebOsPlusConfigEntry, async_luna_request
from .entity import WebOsPlusAgentEntity, WebOsPlusOnEntity, cmd

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebOsPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    entities: list[ButtonEntity] = [InputPickerButton(entry)]
    if entry.runtime_data.agent:
        entities.append(FreeMemoryButton(entry))
    async_add_entities(entities)


class InputPickerButton(WebOsPlusOnEntity, ButtonEntity):
    """Open the TV's input picker on screen."""

    _attr_translation_key = "input_picker"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: WebOsPlusConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "input_picker")

    @cmd
    @override
    async def async_press(self) -> None:
        await async_luna_request(self._client, LUNA_SHOW_INPUT_PICKER, {})


class FreeMemoryButton(WebOsPlusAgentEntity, ButtonEntity):
    """Close apps left running in the background (never the one on screen)."""

    _attr_translation_key = "free_memory"
    _attr_icon = "mdi:broom"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: WebOsPlusConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "free_memory")

    @override
    async def async_press(self) -> None:
        try:
            result = await self.coordinator.async_run("free-memory")
        except AgentError as err:
            raise HomeAssistantError(f"Free memory failed: {err}") from err
        LOGGER.info(
            "%s: closed %s, available memory %s -> %s kB",
            self.coordinator.agent.host,
            result.get("closed"),
            result.get("mem_available_before_kb"),
            result.get("mem_available_after_kb"),
        )
        await self.coordinator.async_request_refresh()
