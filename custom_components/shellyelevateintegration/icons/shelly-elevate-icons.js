// Registers the "shelly-elevate:" icon prefix in the Home Assistant frontend.
// shelly-elevate:display is the integration's glyph (Wall Display with two chevrons), used as the
// sidebar icon. The panel bundle registers the same icon (frontend/src/icons.ts).
const PREFIX = "shelly-elevate";
const ICONS = {
  display:
    "M5.5 3h13A2.5 2.5 0 0 1 21 5.5v13a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 18.5v-13A2.5 2.5 0 0 1 5.5 3z" +
    "M6 5A1 1 0 0 0 5 6v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1z" +
    "M8 11.2 12 7.2l4 4-1.4 1.4L12 10l-2.6 2.6zM8 15.4l4-4 4 4-1.4 1.4-2.6-2.6-2.6 2.6z",
};

window.customIcons = window.customIcons || {};
window.customIcons[PREFIX] = {
  getIcon: async (name) => ({ path: ICONS[name] ?? ICONS.display, viewBox: "0 0 24 24" }),
  getIconList: async () => Object.keys(ICONS).map((name) => ({ name })),
};

// ha-icon gives up on a prefix that is not registered when it first renders (the sidebar often
// renders before this script has run) and never looks again. Re-render those icons.
function* ourIcons(root) {
  for (const el of root.querySelectorAll("*")) {
    if (el.localName === "ha-icon" && typeof el.icon === "string" && el.icon.startsWith(`${PREFIX}:`)) yield el;
    if (el.shadowRoot) yield* ourIcons(el.shadowRoot);
  }
}

async function refresh() {
  for (const el of ourIcons(document)) {
    if (!el._legacy) continue;
    const icon = el.icon;
    el._legacy = false;
    el.icon = undefined;
    await el.updateComplete;
    el.icon = icon;
  }
}

refresh();
for (const delay of [500, 2000, 6000]) setTimeout(refresh, delay);
