"""Selects for LG webOS TV Plus: picture mode, sound mode, sound output, energy saving."""

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
        category="sound", setting="soundMode",
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


class SoundOutputSelect(WebOsPlusOnEntity, SelectEntity):
    """Where sound goes: TV speakers, ARC soundbar, optical, Bluetooth, ..."""

    _attr_translation_key = "sound_output"

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
    """Picture mode. Write-only on the TV without root, so the state is the last one set here."""

    _attr_translation_key = "picture_mode"
    _attr_options = PICTURE_MODES
    _attr_assumed_state = True

    def __init__(self, entry: WebOsPlusConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "picture_mode")

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) and last.state in PICTURE_MODES:
            self.coordinator.picture_mode = last.state

    @property
    @override
    def current_option(self) -> str | None:
        return self.coordinator.picture_mode

    @cmd
    @override
    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_setting("picture", "pictureMode", option)
        self.coordinator.picture_mode = option
        self.async_write_ha_state()
