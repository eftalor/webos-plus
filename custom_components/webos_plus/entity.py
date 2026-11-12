"""Base entity for LG webOS TV Plus."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate, cast

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, WEBOSTV_EXCEPTIONS
from .coordinator import WebOsPlusAgentCoordinator, WebOsPlusConfigEntry, WebOsPlusCoordinator


def device_info(entry: WebOsPlusConfigEntry) -> DeviceInfo:
    """Device info shared by all entities of one TV."""
    info = DeviceInfo(
        identifiers={(DOMAIN, cast(str, entry.unique_id))},
        manufacturer="LG",
        name=entry.title,
    )
    system = entry.runtime_data.client.tv_info.system
    if model := system.get("modelName"):
        info["model"] = model
    if serial := system.get("serialNumber"):
        info["serial_number"] = serial
    return info


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
        self._attr_device_info = device_info(entry)

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


class WebOsPlusAgentEntity(CoordinatorEntity[WebOsPlusAgentCoordinator]):
    """An entity fed by the root agent; available while the TV is on and the agent answers."""

    _attr_has_entity_name = True

    def __init__(self, entry: WebOsPlusConfigEntry, key: str) -> None:
        """Initialize."""
        agent = entry.runtime_data.agent
        assert agent is not None
        super().__init__(agent)
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = device_info(entry)

    @property
    def available(self) -> bool:
        """Available while there is fresh agent data."""
        return super().available and bool(self.coordinator.data)


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
