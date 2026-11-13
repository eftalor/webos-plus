"""Selects for LG webOS TV Plus: input, picture mode, sound mode, sound output, energy saving."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import ENERGY_SAVING, PICTURE_MODES, SOUND_MODES, SOUND_OUTPUTS
from .coordinator import WebOsPlusConfigEntry
from .entity import WebOsPlusOnEntity, cmd

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SettingSelectDescription(SelectEntityDescription):
    """A select backed by a TV system setting."""

    category: str
    setting: str


SETTING_SELECTS = (
    SettingSelectDescription(
        key="sound_mode", translation_key="sound_mode", options=SOUND_MODES,
        category="sound", setting="soundMode", entity_category=EntityCategory.CONFIG,
    ),
    SettingSelectDescription(
        key="energy_saving", translation_key="energy_saving", options=ENERGY_SAVING,
        category="picture", setting="energySaving", entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebOsPlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects."""
    async_add_entities(
        [
            InputSelect(entry),
            PictureModeSelect(entry),
            SoundOutputSelect(entry),
            *(SettingSelect(entry, d) for d in SETTING_SELECTS),
        ]
    )


class SettingSelect(WebOsPlusOnEntity, SelectEntity):
    """Select for a subscribed setting; state comes from the TV's push updates."""

    entity_description: SettingSelectDescription

    def __init__(self, entry: WebOsPlusConfigEntry, description: SettingSelectDescription) -> None:
        """Initialize."""
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    @override
    def current_option(self) -> str | None:
        value = self.coordinator.settings.get(self.entity_description.setting)
        return value if value in self.options else None

    @cmd
    @override
    async def async_select_option(self, option: str) -> None:
        d = self.entity_description
        await self.coordinator.async_set_setting(d.category, d.setting, option)


class InputSelect(WebOsPlusOnEntity, SelectEntity):
    """External input (HDMI, AV, ...) with the names set on the TV.

    While an app is in front, that app is added as an extra option so the state shows
    what is on screen instead of "unknown"; choosing it brings the app to the front.
    """

    _attr_translation_key = "input"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: WebOsPlusConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "input")

    def _foreground_app(self) -> dict | None:
        """The app in front, unless it is one of the inputs."""
        tv = self._client.tv_state
        if any(inp["appId"] == tv.current_app_id for inp in tv.inputs.values()):
            return None
        return tv.apps.get(tv.current_app_id) if tv.current_app_id else None

    @property
    @override
    def options(self) -> list[str]:
        labels = [inp["label"] for inp in self._client.tv_state.inputs.values()]
        if (app := self._foreground_app()) and app["title"] not in labels:
            labels.append(app["title"])
        return labels

    @property
    @override
    def current_option(self) -> str | None:
        tv = self._client.tv_state
        for inp in tv.inputs.values():
            if inp["appId"] == tv.current_app_id:
                return inp["label"]
        app = self._foreground_app()
        return app["title"] if app else None

    @cmd
    @override
    async def async_select_option(self, option: str) -> None:
        for inp in self._client.tv_state.inputs.values():
            if inp["label"] == option:
                await self._client.set_input(inp["id"])
                return
        if (app := self._foreground_app()) and app["title"] == option:
            await self._client.launch_app(app["id"])


class SoundOutputSelect(WebOsPlusOnEntity, SelectEntity):
    """Where sound goes: TV speakers, ARC soundbar, optical, Bluetooth, ..."""

    _attr_translation_key = "sound_output"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: WebOsPlusConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "sound_output")

    @property
    @override
    def options(self) -> list[str]:
        current = self._client.tv_state.sound_output
        if current and current not in SOUND_OUTPUTS:
            return [*SOUND_OUTPUTS, current]
        return SOUND_OUTPUTS

    @property
    @override
    def current_option(self) -> str | None:
        return self._client.tv_state.sound_output

    @cmd
    @override
    async def async_select_option(self, option: str) -> None:
        await self._client.change_sound_output(option)


class PictureModeSelect(WebOsPlusOnEntity, RestoreEntity, SelectEntity):
    """Picture mode.

    Without root the TV won't report it, so the state is the last one set here.
    With the root agent the real value is read every poll (and after a change).
    """

    _attr_translation_key = "picture_mode"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: WebOsPlusConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "picture_mode")
        self._agent = entry.runtime_data.agent
        self._attr_assumed_state = self._agent is None

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._agent:
            self.async_on_remove(self._agent.async_add_listener(self._handle_coordinator_update))
        if (last := await self.async_get_last_state()) and last.state in PICTURE_MODES:
            self.coordinator.picture_mode = last.state

    def _agent_mode(self) -> str | None:
        if self._agent and self._agent.data:
            return self._agent.data.get("picture_mode") or None
        return None

    @property
    @override
    def options(self) -> list[str]:
        # HDR content uses its own modes (hdrStandard, dolbyHdrCinema, ...)
        current = self.current_option
        if current and current not in PICTURE_MODES:
            return [*PICTURE_MODES, current]
        return PICTURE_MODES

    @property
    @override
    def current_option(self) -> str | None:
        return self._agent_mode() or self.coordinator.picture_mode

    @cmd
    @override
    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_setting("picture", "pictureMode", option)
        self.coordinator.picture_mode = option
        if self._agent and self._agent.data:
            self._agent.data["picture_mode"] = option  # until the next read confirms it
        self.async_write_ha_state()
        if self._agent:
            await self._agent.async_request_refresh()
