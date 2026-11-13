"""Sensors for LG webOS TV Plus."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfDataRate, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import WebOsPlusConfigEntry
from .entity import WebOsPlusAgentEntity, WebOsPlusEntity

PARALLEL_UPDATES = 0

POWER_STATES = ["on", "screen_off", "standby", "off"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebOsPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    entities: list[SensorEntity] = [PowerStateSensor(entry), CurrentAppSensor(entry)]
    if entry.runtime_data.agent:
        entities += [AgentSensor(entry, d) for d in AGENT_SENSORS]
    async_add_entities(entities)


def _mib(kb: Any) -> float | None:
    return round(kb / 1024, 1) if isinstance(kb, (int, float)) else None


def _used_pct(d: dict[str, Any]) -> float | None:
    total, avail = d.get("MemTotal_kb"), d.get("MemAvailable_kb")
    if not total or avail is None:
        return None
    return round(100 * (1 - avail / total), 1)


def _swap_used(d: dict[str, Any]) -> float | None:
    total, free = d.get("SwapTotal_kb"), d.get("SwapFree_kb")
    if total is None or free is None:
        return None
    return _mib(total - free)


def _last_boot(d: dict[str, Any]) -> datetime | None:
    up = d.get("uptime_s")
    if not isinstance(up, (int, float)):
        return None
    # whole minutes, so the value doesn't change on every poll
    return (dt_util.utcnow() - timedelta(seconds=up)).replace(second=0, microsecond=0)


def _top(d: dict[str, Any]) -> dict[str, Any]:
    # several processes can share a name (WebAppMgr runs one per web app): add them up
    totals: dict[str, int] = {}
    for name, kb in d.get("top", []):
        totals[name] = totals.get(name, 0) + kb
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    return {"top_processes": {name: _mib(kb) for name, kb in ranked}}


def _mbit(bps: Any) -> float | None:
    return round(bps * 8 / 1_000_000, 3) if isinstance(bps, (int, float)) else None


def _storage(label: str) -> Callable[[dict[str, Any]], float | None]:
    def value(d: dict[str, Any]) -> float | None:
        for name, total, used in d.get("storage", []):
            if name == label and total:
                return round(100 * used / total, 1)
        return None

    return value


def _storage_attrs(label: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def attrs(d: dict[str, Any]) -> dict[str, Any]:
        for name, total, used in d.get("storage", []):
            if name == label:
                return {"total_mib": _mib(total), "used_mib": _mib(used), "free_mib": _mib(total - used)}
        return {}

    return attrs


@dataclass(frozen=True, kw_only=True)
class AgentSensorDescription(SensorEntityDescription):
    """A value from the agent's stats."""

    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


_MEM = {
    "device_class": SensorDeviceClass.DATA_SIZE,
    "native_unit_of_measurement": UnitOfInformation.MEBIBYTES,
    "state_class": SensorStateClass.MEASUREMENT,
    "suggested_display_precision": 0,
    "entity_category": EntityCategory.DIAGNOSTIC,
}
_PCT = {
    "native_unit_of_measurement": PERCENTAGE,
    "state_class": SensorStateClass.MEASUREMENT,
    "suggested_display_precision": 0,
    "entity_category": EntityCategory.DIAGNOSTIC,
}
AGENT_SENSORS = (
    AgentSensorDescription(
        key="memory_free", translation_key="memory_free", icon="mdi:memory",
        value_fn=lambda d: _mib(d.get("MemAvailable_kb")), attrs_fn=_top, **_MEM,
    ),
    AgentSensorDescription(
        key="memory_used", translation_key="memory_used", icon="mdi:memory",
        value_fn=_used_pct, **_PCT,
    ),
    AgentSensorDescription(
        key="swap_used", translation_key="swap_used", icon="mdi:harddisk",
        value_fn=_swap_used, **_MEM,
    ),
    AgentSensorDescription(
        key="cpu", translation_key="cpu", icon="mdi:cpu-64-bit",
        value_fn=lambda d: d.get("cpu_pct"), **_PCT,
    ),
    AgentSensorDescription(
        key="load", translation_key="load", icon="mdi:gauge",
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC, entity_registry_enabled_default=False,
        value_fn=lambda d: d.get("load1"),
    ),
    AgentSensorDescription(
        key="netflix_memory", translation_key="netflix_memory", icon="mdi:netflix",
        value_fn=lambda d: _mib(d.get("netflix_kb")), **_MEM,
    ),
    AgentSensorDescription(
        key="network_in", translation_key="network_in", icon="mdi:download-network",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC, value_fn=lambda d: _mbit(d.get("net_rx_bps")),
    ),
    AgentSensorDescription(
        key="network_out", translation_key="network_out", icon="mdi:upload-network",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC, value_fn=lambda d: _mbit(d.get("net_tx_bps")),
    ),
    AgentSensorDescription(
        key="storage_apps", translation_key="storage_apps", icon="mdi:apps",
        value_fn=_storage("apps"), attrs_fn=_storage_attrs("apps"), **_PCT,
    ),
    AgentSensorDescription(
        key="storage_data", translation_key="storage_data", icon="mdi:database",
        value_fn=_storage("data"), attrs_fn=_storage_attrs("data"), **_PCT,
    ),
    AgentSensorDescription(
        key="last_boot", translation_key="last_boot",
        device_class=SensorDeviceClass.TIMESTAMP, entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_last_boot,
    ),
)


class AgentSensor(WebOsPlusAgentEntity, SensorEntity):
    """A sensor read from the root agent."""

    entity_description: AgentSensorDescription

    def __init__(self, entry: WebOsPlusConfigEntry, description: AgentSensorDescription) -> None:
        """Initialize."""
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if (fn := self.entity_description.attrs_fn) and self.coordinator.data:
            return fn(self.coordinator.data)
        return None


class PowerStateSensor(WebOsPlusEntity, SensorEntity):
    """on / screen_off / standby / off."""

    _attr_translation_key = "power_state"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = POWER_STATES

    def __init__(self, entry: WebOsPlusConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "power_state")

    @property
    @override
    def native_value(self) -> str:
        return self.coordinator.power_state


class CurrentAppSensor(WebOsPlusEntity, SensorEntity):
    """The app or input in the foreground, with its icon."""

    _attr_translation_key = "current_app"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: WebOsPlusConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "current_app")

    @property
    @override
    def native_value(self) -> str | None:
        if not self.coordinator.is_on:
            return None
        tv = self._client.tv_state
        app_id = tv.current_app_id or ""
        if app := tv.apps.get(app_id):
            return app["title"]
        for inp in tv.inputs.values():
            if inp["appId"] == app_id:
                return inp["label"]
        return app_id or None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str | None]:
        return {"app_id": self._client.tv_state.current_app_id if self.coordinator.is_on else None}
