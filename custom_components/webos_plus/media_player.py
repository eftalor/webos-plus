"""Media player for LG webOS TV Plus."""

import asyncio
from contextlib import suppress
from http import HTTPStatus
from typing import Any, override

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LIVE_TV_APP_ID, LOGGER
from .coordinator import WebOsPlusConfigEntry
from .entity import WebOsPlusEntity, cmd

PARALLEL_UPDATES = 0

BASE_FEATURES = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.PLAY_MEDIA
)
VOLUME_FEATURES = (
    MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_SET
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebOsPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the media player."""
    async_add_entities([WebOsPlusMediaPlayer(entry)])


class WebOsPlusMediaPlayer(WebOsPlusEntity, MediaPlayerEntity):
    """The TV as a media player. Off is a state; power on always works."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_name = None

    def __init__(self, entry: WebOsPlusConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry)
        self._sources: dict[str, dict[str, Any]] = {}
        self._paused = False
        self._update_attrs()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self._update_attrs()
        super()._handle_coordinator_update()

    def _update_attrs(self) -> None:
        coord = self.coordinator
        tv = self._client.tv_state
        self._attr_extra_state_attributes = {"power_state": coord.power_state}

        if not coord.is_on:
            self._attr_state = MediaPlayerState.OFF
            self._attr_supported_features = BASE_FEATURES | VOLUME_FEATURES
            self._attr_media_image_url = None
            self._attr_media_title = None
            self._attr_source = None
            self._attr_app_id = None
            self._attr_app_name = None
            self._attr_volume_level = None
            self._attr_is_volume_muted = None
            # keep the last source list so the UI still shows choices
            self._attr_source_list = sorted(self._sources) or None
            return

        self._attr_state = MediaPlayerState.ON
        for item in tv.media_state:
            play_state = item.get("playState")
            if play_state == "playing":
                self._attr_state = MediaPlayerState.PLAYING
            elif play_state == "paused":
                self._attr_state = MediaPlayerState.PAUSED

        features = BASE_FEATURES
        if tv.sound_output != "lineout":
            features |= VOLUME_FEATURES
        self._attr_supported_features = features

        self._attr_volume_level = tv.volume / 100.0 if tv.volume is not None else None
        self._attr_is_volume_muted = tv.muted

        # Sources: apps first, then inputs (with the names set on the TV)
        sources: dict[str, dict[str, Any]] = {}
        current = None
        for app in tv.apps.values():
            sources[app["title"]] = app
            if app["id"] == tv.current_app_id:
                current = app["title"]
        for inp in tv.inputs.values():
            sources[inp["label"]] = inp
            if inp["appId"] == tv.current_app_id:
                current = inp["label"]
        if sources:
            self._sources = sources
        self._attr_source_list = sorted(self._sources)
        self._attr_source = current
        self._attr_app_id = tv.current_app_id
        self._attr_app_name = current

        self._attr_media_content_type = None
        self._attr_media_title = current
        if tv.current_app_id == LIVE_TV_APP_ID:
            self._attr_media_content_type = MediaType.CHANNEL
            if tv.current_channel:
                self._attr_media_title = tv.current_channel.get("channelName")

        self._attr_media_image_url = None
        if app := tv.apps.get(tv.current_app_id or ""):
            icon = app.get("largeIcon") or ""
            self._attr_media_image_url = icon if icon.startswith("http") else app.get("icon")

        self._attr_extra_state_attributes.update(
            {
                "sound_output": tv.sound_output,
                "picture_mode": coord.picture_mode,
                "sound_mode": coord.settings.get("soundMode"),
            }
        )

    @override
    async def async_turn_on(self) -> None:
        """Turn on with Wake-on-LAN."""
        await self.coordinator.async_turn_on()

    @override
    async def async_turn_off(self) -> None:
        """Turn off (no-op if already off)."""
        if self.coordinator.is_on:
            await self._client.power_off()

    @cmd
    @override
    async def async_volume_up(self) -> None:
        await self._client.volume_up()

    @cmd
    @override
    async def async_volume_down(self) -> None:
        await self._client.volume_down()

    @cmd
    @override
    async def async_set_volume_level(self, volume: float) -> None:
        await self._client.set_volume(round(volume * 100))

    @cmd
    @override
    async def async_mute_volume(self, mute: bool) -> None:
        await self._client.set_mute(mute)

    @cmd
    @override
    async def async_select_source(self, source: str) -> None:
        if (item := self._sources.get(source)) is None:
            raise HomeAssistantError(f"Unknown source {source!r}")
        if item.get("title"):
            await self._client.launch_app(item["id"])
        else:
            await self._client.set_input(item["id"])

    @cmd
    @override
    async def async_media_play_pause(self) -> None:
        if self._paused:
            await self.async_media_play()
        else:
            await self.async_media_pause()

    @cmd
    @override
    async def async_media_play(self) -> None:
        self._paused = False
        await self._client.play()

    @cmd
    @override
    async def async_media_pause(self) -> None:
        self._paused = True
        await self._client.pause()

    @cmd
    @override
    async def async_media_stop(self) -> None:
        await self._client.stop()

    @cmd
    @override
    async def async_media_next_track(self) -> None:
        if self._client.tv_state.current_app_id == LIVE_TV_APP_ID:
            await self._client.channel_up()
        else:
            await self._client.fast_forward()

    @cmd
    @override
    async def async_media_previous_track(self) -> None:
        if self._client.tv_state.current_app_id == LIVE_TV_APP_ID:
            await self._client.channel_down()
        else:
            await self._client.rewind()

    @cmd
    @override
    async def async_play_media(self, media_type: MediaType | str, media_id: str, **kwargs: Any) -> None:
        """Play a channel by name or number, or launch an app by id (media_type 'app')."""
        if media_type == "app":
            await self._client.launch_app(media_id)
            return
        if media_type == MediaType.CHANNEL and self._client.tv_state.channels:
            wanted = media_id.lower()
            for channel in self._client.tv_state.channels:
                if wanted in (channel["channelName"].lower(), channel["channelNumber"]):
                    await self._client.set_channel(channel["channelId"])
                    return
            raise HomeAssistantError(f"Channel {media_id!r} not found")
        raise HomeAssistantError(f"Unsupported media type {media_type!r}")

    @override
    async def _async_fetch_image(self, url: str) -> tuple[bytes | None, str | None]:
        """Fetch app icons; the TV uses self-signed certificates."""
        content = None
        session = async_get_clientsession(self.hass)
        with suppress(TimeoutError):
            async with asyncio.timeout(10):
                response = await session.get(url, ssl=False)
                if response.status == HTTPStatus.OK:
                    content = await response.read()
        if content is None:
            LOGGER.debug("Could not fetch image %s", url)
        return content, None
