"""Coordinator for LG webOS TV Plus.

Differences from the built-in webostv coordinator:
- A TV that is off is a normal state, never "unavailable".
- While off, a cheap TCP check runs every few seconds and the websocket
  connects as soon as the port opens, so "on" shows up fast.
- Power on is built in (Wake-on-LAN), no automation needed.
- Picture and sound settings are subscribed to after every (re)connect.
"""

import asyncio
from contextlib import suppress
from datetime import timedelta
import time
from typing import Any, override

from aiowebostv import WebOsClient, WebOsTvPairError, WebOsTvState
from wakeonlan import send_magic_packet

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_SECRET, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .agent import AgentError, TvAgent
from .const import (
    AGENT_POLL,
    AGENT_POLL_LIVE,
    CONF_BROADCAST,
    CONF_MACS,
    DEFAULT_BROADCAST,
    FAST_WINDOW,
    GET_SYSTEM_SETTINGS,
    LOGGER,
    LUNA_SET_SYSTEM_SETTINGS,
    POLL_FAST,
    POLL_OFF,
    STATS_APP_IDS,
    SUBSCRIBED_SETTINGS,
    WEBOSTV_EXCEPTIONS,
    WS_PORT,
)

type WebOsPlusConfigEntry = ConfigEntry[WebOsPlusCoordinator]


async def async_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Return True if a TCP connection to host:port succeeds quickly."""
    try:
        async with asyncio.timeout(timeout):
            _reader, writer = await asyncio.open_connection(host, port)
    except (OSError, TimeoutError):
        return False
    writer.close()
    with suppress(OSError):
        await writer.wait_closed()
    return True


async def async_luna_request(client: WebOsClient, uri: str, params: dict[str, Any]) -> None:
    """Call a luna service through an invisible alert (works without root).

    The TV runs the alert's onclose action with system rights. There is no
    result; read the value back (or rely on a subscription) to confirm.
    """
    buttons = [{"label": "", "onClick": uri, "params": params}]
    payload = {
        "message": " ",
        "buttons": buttons,
        "onclose": {"uri": uri, "params": params},
        "onfail": {"uri": uri, "params": params},
    }
    alert = await client.request("system.notifications/createAlert", payload)
    await client.request("system.notifications/closeAlert", {"alertId": alert["alertId"]})


class WebOsPlusCoordinator(DataUpdateCoordinator[None]):
    """Keep one LG TV connected whenever it is reachable."""

    config_entry: WebOsPlusConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: WebOsPlusConfigEntry, client: WebOsClient
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=POLL_OFF),
        )
        self.client = client
        self.host: str = entry.data[CONF_HOST]
        # Settings pushed by the TV: {"backlight": "100", "soundMode": "standard", ...}
        self.settings: dict[str, Any] = {}
        # Last picture mode set through HA (the TV won't report it without root)
        self.picture_mode: str | None = None
        self._fast_until = 0.0
        # Set up later when the root agent is enabled
        self.agent: WebOsPlusAgentCoordinator | None = None
        self._was_on = False
        self._was_live = False

    @property
    def is_on(self) -> bool:
        """Return True if the TV is on (screen on or off)."""
        return self.client.is_connected() and self.client.tv_state.is_on

    @property
    def power_state(self) -> str:
        """Return a simple power state: on, screen_off, standby or off."""
        if not self.client.is_connected():
            return "off"
        state = self.client.tv_state.power_state.get("state")
        if state == "Screen Off":
            return "screen_off"
        if state in ("Active Standby", "Suspend"):
            return "standby"
        if state == "Power Off":
            return "off"
        return "on" if self.client.tv_state.is_on else "off"

    @override
    async def _async_update_data(self) -> None:
        """Connect if the TV became reachable. Never fails while the TV is off."""
        fast = time.monotonic() < self._fast_until
        self.update_interval = timedelta(seconds=POLL_FAST if fast else POLL_OFF)

        if self.client.is_connected():
            return
        if not await async_port_open(self.host, WS_PORT):
            return

        try:
            await self.client.connect()
        except WebOsTvPairError as err:
            raise ConfigEntryAuthFailed(f"The TV rejected the pairing key: {err}") from err
        except WEBOSTV_EXCEPTIONS as err:
            LOGGER.debug("%s: port open but connect failed: %r", self.host, err)
            return

        self._update_client_key()
        await self._async_subscribe_settings()

    async def _async_subscribe_settings(self) -> None:
        """Subscribe to settings; the library drops subscriptions on reconnect."""
        for category, keys in SUBSCRIBED_SETTINGS.items():

            async def _on_settings(payload: dict[str, Any]) -> None:
                if settings := payload.get("settings"):
                    self.settings.update(settings)
                    self.async_set_updated_data(None)

            try:
                await self.client.subscribe(
                    _on_settings, GET_SYSTEM_SETTINGS, {"category": category, "keys": keys}
                )
            except WEBOSTV_EXCEPTIONS as err:
                LOGGER.debug("%s: settings subscription %s failed: %r", self.host, category, err)
            except Exception as err:  # noqa: BLE001 - response type errors on other models
                LOGGER.warning("%s: settings %s not available: %s", self.host, category, err)

    async def async_handle_update(self, tv_state: WebOsTvState) -> None:
        """Handle a state push from the library (also called on disconnect)."""
        on = self.is_on
        if not self.client.is_connected():
            self.settings.clear()
        live = on and self.client.tv_state.current_app_id in STATS_APP_IDS
        if on != self._was_on or live != self._was_live:
            LOGGER.debug("%s: power %s, stats app %s", self.host, on, live)
            self._was_on, self._was_live = on, live
            if self.agent:
                self.agent.set_live(live)
                # read stats right away instead of waiting for the next poll
                self.hass.async_create_task(self.agent.async_request_refresh())
        self.async_set_updated_data(None)

    @callback
    def _update_client_key(self) -> None:
        """Store a new client key if the TV issued one."""
        entry = self.config_entry
        if self.client.client_key and self.client.client_key != entry.data[CONF_CLIENT_SECRET]:
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_CLIENT_SECRET: self.client.client_key}
            )

    async def async_turn_on(self) -> None:
        """Wake the TV: magic packets to every known MAC, plus turnOn if reachable."""
        macs: list[str] = self.config_entry.data.get(CONF_MACS, [])
        broadcast = self.config_entry.options.get(CONF_BROADCAST, DEFAULT_BROADCAST)
        if macs:
            await self.hass.async_add_executor_job(
                lambda: send_magic_packet(*macs, ip_address=broadcast)
            )
            LOGGER.debug("%s: sent Wake-on-LAN to %s via %s", self.host, macs, broadcast)
        else:
            LOGGER.warning("%s: no MAC address known, cannot send Wake-on-LAN", self.host)
        if self.client.is_connected():
            # Active Standby (Quick Start+) keeps the websocket up.
            with suppress(*WEBOSTV_EXCEPTIONS):
                await self.client.power_on()
        self._fast_until = time.monotonic() + FAST_WINDOW
        await self.async_request_refresh()

    async def async_set_setting(self, category: str, key: str, value: Any) -> None:
        """Change a system setting (picture, sound, ...)."""
        await async_luna_request(
            self.client, LUNA_SET_SYSTEM_SETTINGS, {"category": category, "settings": {key: value}}
        )


class WebOsPlusAgentCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the root agent for memory, CPU and picture mode while the TV is on."""

    config_entry: WebOsPlusConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: WebOsPlusConfigEntry,
        main: WebOsPlusCoordinator,
        agent: TvAgent,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{entry.title} agent",
            update_interval=timedelta(seconds=AGENT_POLL),
        )
        self.main = main
        self.agent = agent
        # previous network byte counters: (monotonic time, rx, tx)
        self._net_prev: tuple[float, int, int] | None = None

    @callback
    def set_live(self, live: bool) -> None:
        """Poll faster while a stats app shows the values on the TV."""
        self.update_interval = timedelta(seconds=AGENT_POLL_LIVE if live else AGENT_POLL)

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Return the agent's stats, or {} while the TV is off."""
        if not self.main.is_on:
            self._net_prev = None
            return {}
        try:
            data = await self.agent.async_run("stats")
        except AgentError as err:
            raise UpdateFailed(str(err)) from err
        self._add_net_rates(data)
        return data

    def _add_net_rates(self, data: dict[str, Any]) -> None:
        """Turn the agent's byte counters into average rates since the last poll."""
        counters = data.get("net_bytes")
        if not (isinstance(counters, list) and len(counters) == 2):
            return
        now, rx, tx = time.monotonic(), int(counters[0]), int(counters[1])
        prev, self._net_prev = self._net_prev, (now, rx, tx)
        if prev is None or now <= prev[0] or rx < prev[1] or tx < prev[2]:
            return  # first poll, or counters reset (TV rebooted)
        secs = now - prev[0]
        data["net_rx_bps"] = (rx - prev[1]) / secs
        data["net_tx_bps"] = (tx - prev[2]) / secs

    async def async_run(self, command: str) -> dict[str, Any]:
        """Run another agent command (free-memory, ...)."""
        return await self.agent.async_run(command)
