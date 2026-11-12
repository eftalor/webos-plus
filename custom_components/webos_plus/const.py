"""Constants for LG webOS TV Plus."""

import asyncio
import logging

import aiohttp
from aiowebostv import WebOsTvCommandError

from homeassistant.const import Platform

DOMAIN = "webos_plus"
LOGGER = logging.getLogger(__package__)
PLATFORMS = [
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]
DEFAULT_NAME = "LG TV"

CONF_MACS = "macs"
CONF_BROADCAST = "broadcast_address"
DEFAULT_BROADCAST = "255.255.255.255"

WS_PORT = 3000
PAIRING_TIMEOUT = 60  # seconds the user gets to accept the prompt on the TV
POLL_OFF = 5  # seconds between reachability checks while the TV is off
POLL_FAST = 1  # seconds between checks right after a turn-on request
FAST_WINDOW = 45  # how long to poll fast after a turn-on request

LIVE_TV_APP_ID = "com.webos.app.livetv"

LUNA_SET_SYSTEM_SETTINGS = "luna://com.webos.settingsservice/setSystemSettings"
LUNA_SHOW_INPUT_PICKER = "luna://com.webos.surfacemanager/showInputPicker"
GET_SYSTEM_SETTINGS = "settings/getSystemSettings"

# Settings that SSAP lets us read and subscribe to (verified on webOS 6.0).
# pictureMode is NOT readable this way; it is write-only without root.
SUBSCRIBED_SETTINGS: dict[str, list[str]] = {
    "picture": ["backlight", "brightness", "contrast", "color", "energySaving"],
    "sound": ["soundMode"],
}

# Values from getSystemSettingDesc on a 2021 UP75 (webOS 6.0), visible ones only.
PICTURE_MODES = [
    "vivid", "normal", "eco", "cinema", "sports", "game", "filmMaker", "expert1", "expert2",
]
ENERGY_SAVING = ["auto", "off", "min", "med", "max"]
SOUND_MODES = [
    "aiSoundPlus", "aiSound", "standard", "movie", "news", "sports", "music", "game",
]
# Labels for the media player's sound mode list (the popup shows these strings)
SOUND_MODE_LABELS = {
    "aiSoundPlus": "AI Sound Pro", "aiSound": "AI Sound", "standard": "Standard",
    "movie": "Cinema", "news": "Clear voice", "sports": "Sports", "music": "Music",
    "game": "Game",
}
SOUND_OUTPUTS = [
    "tv_speaker", "external_arc", "external_optical", "bt_soundbar", "headphone",
    "lineout", "tv_external_speaker", "tv_speaker_headphone",
]

WEBOSTV_EXCEPTIONS = (
    ConnectionResetError,
    OSError,
    WebOsTvCommandError,
    aiohttp.ClientConnectorError,
    aiohttp.ClientError,
    aiohttp.ServerDisconnectedError,
    aiohttp.WSMessageTypeError,
    asyncio.CancelledError,
    asyncio.TimeoutError,
)
