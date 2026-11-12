"""Config flow for LG webOS TV Plus."""

from collections.abc import Mapping
from typing import Any, override

from aiowebostv import WebOsClient, WebOsTvPairError, webos_client
import probatio as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import (
    CONF_BROADCAST,
    CONF_MACS,
    DEFAULT_BROADCAST,
    DEFAULT_NAME,
    DOMAIN,
    PAIRING_TIMEOUT,
    WEBOSTV_EXCEPTIONS,
)
from .coordinator import WebOsPlusConfigEntry


async def async_pair(hass: HomeAssistant, host: str, key: str | None) -> WebOsClient:
    """Connect (and pair if needed), giving the user time to accept on the TV.

    aiowebostv waits only RECEIVE_TIMEOUT (10 s) for the prompt; raise it while pairing.
    """
    client = WebOsClient(host, key, client_session=async_get_clientsession(hass))
    saved = webos_client.RECEIVE_TIMEOUT
    webos_client.RECEIVE_TIMEOUT = max(saved, PAIRING_TIMEOUT)
    try:
        await client.connect()
    finally:
        webos_client.RECEIVE_TIMEOUT = saved
    return client


def _macs(client: WebOsClient) -> list[str]:
    """Return the TV's wired and Wi-Fi MACs, as reported by the TV."""
    conn = client.tv_info.connection
    return [
        format_mac(mac)
        for key in ("wiredInfo", "wifiInfo")
        if (mac := conn.get(key, {}).get("macAddress"))
    ]


class WebOsPlusFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._host = ""
        self._name = DEFAULT_NAME

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: WebOsPlusConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return WebOsPlusOptionsFlow()

    @override
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the TV's address."""
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._name = user_input.get(CONF_NAME) or DEFAULT_NAME
            self._async_abort_entries_match({CONF_HOST: self._host})
            return await self.async_step_pairing()
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_pairing(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pair: the TV shows a prompt that must be accepted with the remote."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                client = await async_pair(self.hass, self._host, None)
            except WebOsTvPairError:
                errors["base"] = "error_pairing"
            except WEBOSTV_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    client.tv_info.hello["deviceUUID"], raise_on_progress=False
                )
                self._abort_if_unique_id_configured({CONF_HOST: self._host})
                data = {
                    CONF_HOST: self._host,
                    CONF_CLIENT_SECRET: client.client_key,
                    CONF_MACS: _macs(client),
                }
                await client.disconnect()
                return self.async_create_entry(title=self._name, data=data)
        return self.async_show_form(
            step_id="pairing",
            errors=errors,
            description_placeholders={"host": self._host, "timeout": str(PAIRING_TIMEOUT)},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The TV forgot us; pair again."""
        self._host = entry_data[CONF_HOST]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-pairing."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                client = await async_pair(self.hass, self._host, None)
            except WebOsTvPairError:
                errors["base"] = "error_pairing"
            except WEBOSTV_EXCEPTIONS:
                errors["base"] = "cannot_connect"
            else:
                entry = self._get_reauth_entry()
                data = {**entry.data, CONF_CLIENT_SECRET: client.client_key}
                if macs := _macs(client):
                    data[CONF_MACS] = macs
                await client.disconnect()
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            errors=errors,
            description_placeholders={"host": self._host, "timeout": str(PAIRING_TIMEOUT)},
        )


class WebOsPlusOptionsFlow(OptionsFlow):
    """Options: Wake-on-LAN broadcast address and MACs."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        entry = self.config_entry
        if user_input is not None:
            macs = [format_mac(m.strip()) for m in user_input.pop(CONF_MACS, "").split(",") if m.strip()]
            self.hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_MACS: macs})
            return self.async_create_entry(title="", data=user_input)
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_BROADCAST,
                    default=entry.options.get(CONF_BROADCAST, DEFAULT_BROADCAST),
                ): cv.string,
                vol.Optional(
                    CONF_MACS, default=", ".join(entry.data.get(CONF_MACS, []))
                ): cv.string,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
