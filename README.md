# LG webOS TV Plus

A Home Assistant custom integration for LG webOS TVs, built on the same
[`aiowebostv`](https://github.com/home-assistant-libs/aiowebostv) library as the
built-in **LG webOS TV** integration, with a few things the built-in one doesn't do.

> Status: early (0.2.0). Tested on one LG 55UP7550 (webOS 6.0, 2021) with Home Assistant 2026.11.

## What's different

| | Built-in `webostv` | LG webOS TV Plus |
|---|---|---|
| TV off | entity becomes *unavailable* | entity is **off**, everything stays usable |
| Turn on | needs your own Wake-on-LAN automation | **built in** (MACs are picked up while pairing) |
| Noticing the TV turned on | reconnect attempt every 10 s | cheap port check every 5 s, every 1 s after a turn-on request |
| Picture/sound settings | — | backlight, brightness, contrast, color, energy saving, sound mode, picture mode |
| Sound output | service call only | select entity |
| More-info popup | play/pause, volume, source | adds **Browse** (apps and inputs with their icons, tap to launch) and **sound mode** |
| Power state | on/off | sensor: on, screen off, standby, off |
| Pairing | 10 s to accept on the TV | 60 s |

Settings are changed without root (the TV runs a `luna://` call on behalf of an
invisible notification) and are kept in sync by subscriptions, so changes made
with the physical remote show up immediately.

**Picture mode** can be set but not read back without root on webOS 6, so its
state is the last value set from Home Assistant, unless the optional root agent
is enabled (see below).

## Entities

- `media_player`: power, volume, apps and inputs (with the names set on the TV), app icon,
  media browser with app icons, sound mode
- `select`: picture mode, sound mode, sound output, energy saving
- `number`: backlight, brightness (contrast and color are disabled by default)
- `switch`: screen (turn the panel off while sound keeps playing)
- `button`: show the input picker
- `sensor`: power state, current app

With the root agent: `sensor` free memory (attribute: top 5 processes), memory used,
swap used, CPU, Netflix memory, last boot, load (disabled by default); `button` free
memory; and the picture mode select shows the TV's real value.

## Services

Same names and fields as the built-in integration, so remote cards written for it work
once their actions point at `webos_plus` instead of `webostv`:
`webos_plus.button` (`button: LEFT`), `webos_plus.command` (`command`, optional `payload`),
`webos_plus.select_sound_output` (`sound_output`).

For the [LG WebOS Remote Control card](https://github.com/madmicio/LG-WebOS-Remote-Control),
which calls `webostv.*` directly, override each key, for example:

```yaml
keys:
  UP:
    service: webos_plus.button
    data: {entity_id: media_player.my_tv, button: UP}
  PLAY:
    service: webos_plus.command
    data: {entity_id: media_player.my_tv, command: media.controls/play}
```

## Install

1. Copy `custom_components/webos_plus` into your Home Assistant `config/custom_components/`
   (or add this repository as a custom repository in Marketplace/HACS).
2. Restart Home Assistant.
3. Settings → Devices & services → Add integration → **LG webOS TV Plus**.
4. Enter the TV's IP address, press Submit, and accept the prompt on the TV.

On the TV, turn on **Turn on via Wi-Fi** (sometimes "Mobile TV On") so Wake-on-LAN works,
and give the TV a fixed IP address.

It can run next to the built-in integration (the TV accepts several paired apps).

## Root agent (optional, rooted TVs only)

On a TV rooted with [webOS Homebrew](https://www.webosbrew.org/) the integration can read
what SSAP won't tell it. It runs `tv/agent.sh` over SSH as the *forced command* of a key that
Home Assistant generates, so that key can only run the agent's fixed commands
(`version`, `stats`, `free-memory`) and never gets a shell. `stats` is polled every 30 s
while the TV is on and takes about a second on the TV.

1. Copy `tv/agent.sh` to `/var/lib/webos-plus/agent` on the TV and `chmod 755` it.
2. In Home Assistant: the integration's **Configure** → tick **Root agent** → Submit.
   The next step shows a line beginning with `command="/var/lib/webos-plus/agent",...`.
3. Append that line to `/home/root/.ssh/authorized_keys` on the TV, then press Submit.
   The TV's SSH host key is pinned on the first successful test.

**Free memory** closes apps left running in the background. It never closes the app on
screen, Home, inputs, Live TV, AirPlay or the screensaver.

## Roadmap

- Notifications (toasts) and more settings.

## License

MIT
