"""Selects for LG webOS TV Plus."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    ASPECT_RATIOS,
    DYNAMIC_CONTRAST,
    ENERGY_SAVING,
    EYE_COMFORT,
    GAMMA,
    HDR_TONE_MAPPING,
    MENU_LANGUAGES,
    PICTURE_MODES,
    SLEEP_TIMER,
    SOUND_MODES,
    SOUND_OUTPUTS,
    TRUMOTION,
)
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

# The TV often refuses to read these. The select keeps the last value set here.
ASSUMED_SELECTS = (
    SettingSelectDescription(
        key="eye_comfort", translation_key="eye_comfort", icon="mdi:eye-outline",
        options=EYE_COMFORT, category="picture", setting="eyeComfortMode",
        entity_category=EntityCategory.CONFIG,
    ),
    SettingSelectDescription(
        key="sleep_timer", translation_key="sleep_timer", icon="mdi:timer-sand",
        options=SLEEP_TIMER, category="time", setting="sleepTimer",
        entity_category=EntityCategory.CONFIG,
    ),
    SettingSelectDescription(
        key="dynamic_contrast", translation_key="dynamic_contrast", icon="mdi:contrast-box",
        options=DYNAMIC_CONTRAST, category="picture", setting="dynamicContrast",
        entity_category=EntityCategory.CONFIG,
    ),
    SettingSelectDescription(
        key="trumotion", translation_key="trumotion", icon="mdi:motion-play",
        options=TRUMOTION, category="picture", setting="truMotionMode",
        entity_category=EntityCategory.CONFIG,
    ),
    SettingSelectDescription(
        key="gamma", translation_key="gamma", icon="mdi:gamma",
        options=GAMMA, category="picture", setting="gamma",
        entity_category=EntityCategory.CONFIG,
    ),
    SettingSelectDescription(
        key="hdr_tone_mapping", translation_key="hdr_tone_mapping", icon="mdi:hdr",
        options=HDR_TONE_MAPPING, category="picture", setting="hdrDynamicToneMapping",
        entity_category=EntityCategory.CONFIG,
    ),
    SettingSelectDescription(
        key="aspect_ratio", translation_key="aspect_ratio", icon="mdi:aspect-ratio",
        options=ASPECT_RATIOS, category="aspectRatio", setting="arcPerApp",
        entity_category=EntityCategory.CONFIG,
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
            *(AssumedSettingSelect(entry, d) for d in ASSUMED_SELECTS),
            MenuLanguageSelect(entry),
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
        self.coordinator.settings[d.setting] = option
        self.async_write_ha_state()


class AssumedSettingSelect(WebOsPlusOnEntity, RestoreEntity, SelectEntity):
    """A setting the TV may not report. The state is the last value set here."""

    entity_description: SettingSelectDescription

    def __init__(self, entry: WebOsPlusConfigEntry, description: SettingSelectDescription) -> None:
        """Initialize."""
        super().__init__(entry, description.key)
        self.entity_description = description
        self._restored: str | None = None

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in self.options:
            self._restored = last.state

    @property
    @override
    def assumed_state(self) -> bool:
        return self.entity_description.setting not in self.coordinator.live_settings

    @property
    @override
    def current_option(self) -> str | None:
        value = self.coordinator.settings.get(self.entity_description.setting)
        if value in self.options:
            return value
        return self._restored if self._restored in self.options else None

    @cmd
    @override
    async def async_select_option(self, option: str) -> None:
        d = self.entity_description
        await self.coordinator.async_set_setting(d.category, d.setting, option)
        self.coordinator.settings[d.setting] = option
        self._restored = option
        self.async_write_ha_state()


def _menu_tag(info: object) -> str | None:
    """Return the menu locale from a localeInfo object."""
    if not isinstance(info, dict):
        return None
    locales = info.get("locales")
    if not isinstance(locales, dict):
        return None
    tag = locales.get("UI") or locales.get("TV")
    return tag if isinstance(tag, str) and tag else None


class MenuLanguageSelect(WebOsPlusOnEntity, SelectEntity):
    """On-screen menu language. The TV stores this in localeInfo, not menuLanguage."""

    _attr_translation_key = "menu_language"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:translate"

    def __init__(self, entry: WebOsPlusConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry, "menu_language")

    @property
    @override
    def options(self) -> list[str]:
        current = _menu_tag(self.coordinator.settings.get("localeInfo"))
        if current and current not in MENU_LANGUAGES:
            return [*MENU_LANGUAGES, current]
        return MENU_LANGUAGES

    @property
    @override
    def assumed_state(self) -> bool:
        return "localeInfo" not in self.coordinator.live_settings

    @property
    @override
    def current_option(self) -> str | None:
        return _menu_tag(self.coordinator.settings.get("localeInfo"))

    @cmd
    @override
    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_menu_language(option)
        self.async_write_ha_state()


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
