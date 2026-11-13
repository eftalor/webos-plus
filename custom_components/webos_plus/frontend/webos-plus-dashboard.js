// LG webOS TV Plus: a dashboard that builds itself for every TV of this integration.
//
// Add it in Settings -> Dashboards -> Add dashboard -> "LG webOS TV Plus", or in YAML:
//   strategy:
//     type: custom:webos-plus
//     # all optional:
//     entity: media_player.my_tv        # only this TV (default: one view per TV)
//     sources:                          # app buttons on the remote
//       - {name: Netflix, icon: mdi:netflix}
//     color_buttons: true               # show RED/GREEN/YELLOW/BLUE
//
// The remote is madmicio's LG WebOS Remote Control card (MIT), bundled in
// frontend/lg-remote-control.js; see THIRD_PARTY_NOTICES.md.

const BASE = new URL(".", import.meta.url).pathname.replace(/\/$/, "");
const VERSION = new URL(import.meta.url).searchParams.get("v") || "";
const DOMAIN = "webos_plus";
const CARD = "lg-remote-control";

// Remote buttons sent as key presses; media keys sent as SSAP commands.
const BUTTON_KEYS = [
  "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
  "UP", "DOWN", "LEFT", "RIGHT", "ENTER", "BACK", "HOME", "EXIT", "MENU", "INFO",
  "MUTE", "CHANNELUP", "CHANNELDOWN", "RED", "GREEN", "YELLOW", "BLUE",
];
const MEDIA_KEYS = {
  PLAY: "play", PAUSE: "pause", STOP: "stop", REWIND: "rewind",
  FAST_FOWARD: "fastForward", // (sic) the card's key name
  RECORD: "Record",
};
// App buttons offered by default, if the TV has the app.
const DEFAULT_SOURCES = [
  { name: "Netflix", icon: "mdi:netflix" },
  { name: "YouTube", icon: "mdi:youtube" },
  { name: "Prime Video", icon: "amazon" },
  { name: "Disney+", icon: "disney" },
  { name: "HBO Max", icon: "mdi:movie-open-play" },
  { name: "Apple TV", icon: "mdi:apple" },
  { name: "Spotify", icon: "mdi:spotify" },
];

async function ensureCard() {
  if (customElements.get(CARD)) return; // already loaded (e.g. installed through HACS)
  try {
    await import(`${BASE}/lg-remote-control.js?v=${VERSION}`);
  } catch (err) {
    console.error("webos_plus: could not load the remote card", err);
  }
}

const slug = (s) => (s || "tv").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "tv";

function keyMap(entity) {
  const keys = {};
  for (const b of BUTTON_KEYS) {
    keys[b] = { service: `${DOMAIN}.button`, data: { entity_id: entity, button: b } };
  }
  for (const [k, cmd] of Object.entries(MEDIA_KEYS)) {
    keys[k] = { service: `${DOMAIN}.command`, data: { entity_id: entity, command: `media.controls/${cmd}` } };
  }
  return keys;
}

function defaultSources(hass, entity) {
  const list = hass.states[entity]?.attributes?.source_list || [];
  const found = DEFAULT_SOURCES.filter((s) => list.includes(s.name));
  return (found.length ? found : DEFAULT_SOURCES).slice(0, 4);
}

const press = (entity) => ({
  action: "perform-action", perform_action: "button.press", target: { entity_id: entity },
});

function tvView(hass, config, player, entities) {
  // find this TV's entity by its translation key (names and ids can be changed by the user)
  const find = (domain, key) =>
    entities.find((e) => e.entity_id.startsWith(`${domain}.`) && e.translation_key === key)?.entity_id;
  const mp = player.entity_id;
  const device = hass.devices?.[player.device_id];
  const name = device?.name_by_user || device?.name || hass.states[mp]?.attributes?.friendly_name || "TV";

  const tile = (entity, extra = {}) => (entity ? [{ type: "tile", entity, ...extra }] : []);
  const full = { grid_options: { columns: 12 } };
  const half = { grid_options: { columns: 6 } };
  const select = { features: [{ type: "select-options" }], features_position: "bottom" };

  const power = find("sensor", "power_state");
  const sections = [
    {
      type: "grid",
      cards: [
        {
          type: "heading", heading: "TV", icon: "mdi:television",
          badges: power ? [{ type: "entity", entity: power, show_icon: true, show_state: true }] : [],
        },
        ...tile(mp, {
          name: "TV", ...full, state_content: ["state", "source"],
          features: [{ type: "media-player-volume-slider" }], features_position: "bottom",
        }),
        {
          type: `custom:${CARD}`, entity: mp, name, ...full,
          sources: config.sources || defaultSources(hass, mp),
          ...(config.color_buttons ? { color_buttons: "enable" } : {}),
          keys: keyMap(mp),
        },
      ],
    },
    {
      type: "grid",
      cards: [
        { type: "heading", heading: "Picture & sound", heading_style: "subtitle" },
        ...tile(find("select", "picture_mode"), { name: "Picture", ...full, ...select }),
        ...tile(find("number", "backlight"), {
          name: "Backlight", ...full,
          features: [{ type: "numeric-input", style: "slider" }], features_position: "bottom",
        }),
        ...tile(find("select", "sound_output"), { name: "Sound output", ...full, ...select }),
        ...tile(find("select", "sound_mode"), { name: "Sound mode", ...full, ...select }),
        ...tile(find("switch", "screen"), { name: "Screen", ...half }),
        ...tile(find("select", "input"), { name: "Input", ...half, ...select }),
      ],
    },
  ];

  // Root agent entities exist only when that option is on.
  const free = find("sensor", "memory_free");
  if (free) {
    const boot = find("sensor", "last_boot");
    const button = find("button", "free_memory");
    sections.push({
      type: "grid",
      cards: [
        {
          type: "heading", heading: "TV health", icon: "mdi:heart-pulse",
          badges: boot ? [{ type: "entity", entity: boot, show_state: true, state_content: ["name", "state"] }] : [],
        },
        ...tile(free, { name: "Free memory", ...half }),
        ...tile(find("sensor", "cpu"), { name: "CPU", ...half }),
        ...tile(find("sensor", "swap_used"), { name: "Swap used", ...half }),
        ...tile(find("sensor", "netflix_memory"), { name: "Netflix", ...half }),
        ...tile(button, { name: "Free memory", icon: "mdi:broom", hide_state: true, tap_action: press(button) }),
        {
          type: "history-graph", title: "Free memory (24 h)", hours_to_show: 24,
          entities: [{ entity: free, name: "Free memory" }],
        },
      ],
    });
  }

  return {
    title: name, path: slug(name), icon: "mdi:television",
    type: "sections", max_columns: 2, sections,
  };
}

class WebOsPlusDashboardStrategy extends HTMLElement {
  static async generate(config, hass) {
    await ensureCard();
    const all = Object.values(hass.entities || {}).filter((e) => e.platform === DOMAIN && !e.hidden);
    let players = all.filter((e) => e.entity_id.startsWith("media_player."));
    if (config.entity) players = players.filter((e) => e.entity_id === config.entity);
    if (!players.length) {
      return {
        views: [{
          title: "LG webOS TV Plus",
          cards: [{
            type: "markdown",
            content: "No TV found. Add one in **Settings → Devices & services → Add integration → LG webOS TV Plus**.",
          }],
        }],
      };
    }
    return {
      views: players.map((p) => tvView(hass, config, p, all.filter((e) => e.device_id === p.device_id))),
    };
  }
}

customElements.define("ll-strategy-dashboard-webos-plus", WebOsPlusDashboardStrategy);
window.customStrategies = window.customStrategies || [];
if (!window.customStrategies.some((s) => s.type === "webos-plus")) {
  window.customStrategies.push({
    type: "webos-plus",
    strategyType: "dashboard",
    name: "LG webOS TV Plus",
    description: "Remote, picture and sound settings and TV health for your LG TVs.",
  });
}
