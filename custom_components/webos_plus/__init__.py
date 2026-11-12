"""LG webOS TV Plus: a friendlier LG webOS TV integration."""

from aiowebostv import WebOsClient

from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS
from .coordinator import WebOsPlusConfigEntry, WebOsPlusCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: WebOsPlusConfigEntry) -> bool:
    """Set up a TV from a config entry. Works even if the TV is off."""
    client = WebOsClient(
        entry.data[CONF_HOST],
        entry.data[CONF_CLIENT_SECRET],
        client_session=async_get_clientsession(hass),
    )
    entry.runtime_data = coordinator = WebOsPlusCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    await client.register_state_update_callback(coordinator.async_handle_update)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_on_stop(_event: Event) -> None:
        client.clear_state_update_callbacks()
        await client.disconnect()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_on_stop))
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    return True


async def _async_reload_on_options(hass: HomeAssistant, entry: WebOsPlusConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: WebOsPlusConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        client = entry.runtime_data.client
        client.clear_state_update_callbacks()
        await client.disconnect()
    return unloaded
