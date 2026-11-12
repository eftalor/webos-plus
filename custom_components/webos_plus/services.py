"""Entity services for LG webOS TV Plus (same names and fields as the built-in webostv)."""

import probatio as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import ATTR_COMMAND
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

ATTR_BUTTON = "button"
ATTR_PAYLOAD = "payload"
ATTR_SOUND_OUTPUT = "sound_output"

SERVICES = (
    ("button", {vol.Required(ATTR_BUTTON): cv.string}, "async_button", SupportsResponse.NONE),
    (
        "command",
        {vol.Required(ATTR_COMMAND): cv.string, vol.Optional(ATTR_PAYLOAD): dict},
        "async_command",
        SupportsResponse.OPTIONAL,
    ),
    (
        "select_sound_output",
        {vol.Required(ATTR_SOUND_OUTPUT): cv.string},
        "async_select_sound_output",
        SupportsResponse.NONE,
    ),
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the entity services."""
    for name, schema, method, supports_response in SERVICES:
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            name,
            entity_domain=MEDIA_PLAYER_DOMAIN,
            schema=schema,
            func=method,
            supports_response=supports_response,
        )
