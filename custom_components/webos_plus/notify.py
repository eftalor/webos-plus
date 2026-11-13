"""On-screen messages for LG webOS TV Plus."""

from typing import override

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
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
    """Set up the notify entity."""
    async_add_entities([WebOsNotify(entry)])


class WebOsNotify(WebOsPlusOnEntity, NotifyEntity):
    """Show a short toast on the TV screen."""

    _attr_translation_key = "notification"
    _attr_icon = "mdi:message-text"
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, entry: WebOsPlusConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "notification")

    @cmd
    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Show the message. It disappears on its own."""
        await self.coordinator.async_show_toast(message, title)
