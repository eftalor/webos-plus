"""Base entity for LG webOS TV Plus."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate, cast

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, WEBOSTV_EXCEPTIONS
from .coordinator import WebOsPlusConfigEntry, WebOsPlusCoordinator


class WebOsPlusEntity(CoordinatorEntity[WebOsPlusCoordinator]):
    """Base entity. Always available; the TV being off is a state, not an error."""

    _attr_has_entity_name = True

    def __init__(self, entry: WebOsPlusConfigEntry, key: str | None = None) -> None:
        """Initialize."""
        super().__init__(entry.runtime_data)
        self._entry = entry
        self._client = entry.runtime_data.client
        uid = cast(str, entry.unique_id)
        self._attr_unique_id = f"{uid}_{key}" if key else uid
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, uid)},
            manufacturer="LG",
            name=entry.title,
        )
        system = self._client.tv_info.system
        if model := system.get("modelName"):
            self._attr_device_info["model"] = model
        if serial := system.get("serialNumber"):
            self._attr_device_info["serial_number"] = serial

    @property
    def available(self) -> bool:
        """Entities are always available (a TV that is off is still there)."""
        return True


class WebOsPlusOnEntity(WebOsPlusEntity):
    """An entity that only makes sense while the TV is on."""

    @property
    def available(self) -> bool:
        """Available only while the TV is on."""
        return self.coordinator.is_on


def cmd[_EntityT: WebOsPlusEntity, _R, **_P](
    func: Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, _R]],
) -> Callable[Concatenate[_EntityT, _P], Coroutine[Any, Any, _R]]:
    """Refuse commands while the TV is off and turn library errors into HA errors."""

    @wraps(func)
    async def wrapper(self: _EntityT, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        if not self.coordinator.is_on:
            raise HomeAssistantError(f"{self.coordinator.name} is off")
        try:
            return await func(self, *args, **kwargs)
        except WEBOSTV_EXCEPTIONS as err:
            raise HomeAssistantError(
                f"{self.coordinator.name}: {func.__name__} failed: {err!r}"
            ) from err

    return wrapper
