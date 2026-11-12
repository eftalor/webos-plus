"""LG webOS TV Plus: a friendlier LG webOS TV integration."""

from pathlib import Path

from aiowebostv import WebOsClient

from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .agent import TvAgent
from .const import CONF_AGENT, CONF_AGENT_HOST_KEY, CONF_AGENT_KEY, DOMAIN, PLATFORMS
from .coordinator import WebOsPlusAgentCoordinator, WebOsPlusConfigEntry, WebOsPlusCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

STATIC_URL = f"/{DOMAIN}_static"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services and the dashboard (strategy + bundled remote card) once."""
    async_setup_services(hass)
    if hass.http is not None:
        version = (await async_get_integration(hass, DOMAIN)).version
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), True)]
        )
        add_extra_js_url(hass, f"{STATIC_URL}/webos-plus-dashboard.js?v={version}")
    return True


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

    data = entry.data
    if entry.options.get(CONF_AGENT) and data.get(CONF_AGENT_KEY) and data.get(CONF_AGENT_HOST_KEY):
        agent = await hass.async_add_executor_job(
            TvAgent, data[CONF_HOST], data[CONF_AGENT_KEY], data[CONF_AGENT_HOST_KEY]
        )
        coordinator.agent = WebOsPlusAgentCoordinator(hass, entry, coordinator, agent)
        # not first_refresh: a failing agent must not stop the TV from loading
        await coordinator.agent.async_refresh()
        entry.async_on_unload(agent.async_close)

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
