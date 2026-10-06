// Registers the "shelly-elevate:" icon prefix in the Home Assistant frontend.
// shelly-elevate:display is the integration's glyph (Wall Display with two chevrons), used as the
// sidebar icon; tools/make_brand.py draws the same shape for the brand images.
const ICONS = {
  display:
    "M5.5 3h13A2.5 2.5 0 0 1 21 5.5v13a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 18.5v-13A2.5 2.5 0 0 1 5.5 3z" +
    "M6 5A1 1 0 0 0 5 6v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1z" +
    "M8 11.2 12 7.2l4 4-1.4 1.4L12 10l-2.6 2.6zM8 15.4l4-4 4 4-1.4 1.4-2.6-2.6-2.6 2.6z",
};

window.customIcons = window.customIcons || {};
window.customIcons["shelly-elevate"] = {
  getIcon: async (name) => ({ path: ICONS[name] ?? ICONS.display, viewBox: "0 0 24 24" }),
  getIconList: async () => Object.keys(ICONS).map((name) => ({ name })),
};
