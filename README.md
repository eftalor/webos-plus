# LG webOS TV Plus

A Home Assistant custom integration for LG webOS TVs, built on the same
[`aiowebostv`](https://github.com/home-assistant-libs/aiowebostv) library as the
built-in **LG webOS TV** integration, with a few things the built-in one doesn't do.

> Status: early (0.1.0). Tested on one LG 55UP7550 (webOS 6.0, 2021) with Home Assistant 2026.11.

## What's different

| | Built-in `webostv` | LG webOS TV Plus |
|---|---|---|
| TV off | entity becomes *unavailable* | entity is **off**, everything stays usable |
| Turn on | needs your own Wake-on-LAN automation | **built in** (MACs are picked up while pairing) |
| Noticing the TV turned on | reconnect attempt every 10 s | cheap port check every 5 s, every 1 s after a turn-on request |
| Picture/sound settings | — | backlight, brightness, contrast, color, energy saving, sound mode, picture mode |
| Sound output | service call only | select entity |
| Power state | on/off | sensor: on, screen off, standby, off |
| Pairing | 10 s to accept on the TV | 60 s |

Settings are changed without root (the TV runs a `luna://` call on behalf of an
invisible notification) and are kept in sync by subscriptions, so changes made
with the physical remote show up immediately.

**Picture mode** can be set but not read back without root on webOS 6, so its
state is the last value set from Home Assistant.

## Entities

- `media_player`: power, volume, apps and inputs (with the names set on the TV), app icon
- `select`: picture mode, sound mode, sound output, energy saving
- `number`: backlight, brightness (contrast and color are disabled by default)
- `switch`: screen (turn the panel off while sound keeps playing)
- `button`: show the input picker
- `sensor`: power state, current app

## Install

1. Copy `custom_components/webos_plus` into your Home Assistant `config/custom_components/`
   (or add this repository as a custom repository in Marketplace/HACS).
2. Restart Home Assistant.
3. Settings → Devices & services → Add integration → **LG webOS TV Plus**.
4. Enter the TV's IP address, press Submit, and accept the prompt on the TV.

On the TV, turn on **Turn on via Wi-Fi** (sometimes "Mobile TV On") so Wake-on-LAN works,
and give the TV a fixed IP address.

It can run next to the built-in integration (the TV accepts several paired apps).

## Roadmap

- Optional root features over SSH for rooted TVs (webOS Homebrew): memory, swap and CPU
  sensors, reading the real picture mode, freeing memory. Uses a restricted key and a
  helper script with a fixed command list.
- Notifications (toasts) and more settings.

## License

MIT
