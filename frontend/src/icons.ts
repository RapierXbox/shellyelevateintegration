/**
 * The integration's own glyph (Wall Display with two chevrons), the same path as
 * `shelly-elevate:display` in custom_components/shellyelevateintegration/icons/shelly-elevate-icons.js
 * (the sidebar icon). Single path, viewBox 0 0 24 24, usable as `ha-svg-icon` `.path`.
 */
export const mdiShellyElevateDisplay =
  "M5.5 3h13A2.5 2.5 0 0 1 21 5.5v13a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 18.5v-13A2.5 2.5 0 0 1 5.5 3z" +
  "M6 5A1 1 0 0 0 5 6v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1z" +
  "M8 11.2 12 7.2l4 4-1.4 1.4L12 10l-2.6 2.6zM8 15.4l4-4 4 4-1.4 1.4-2.6-2.6-2.6 2.6z";

const PREFIX = "shelly-elevate";

type IconElement = HTMLElement & { icon?: string; _legacy?: boolean; updateComplete?: Promise<unknown> };

function* ourIcons(root: Document | ShadowRoot): Generator<IconElement> {
  for (const el of root.querySelectorAll<IconElement>("*")) {
    if (el.localName === "ha-icon" && el.icon?.startsWith(`${PREFIX}:`)) yield el;
    if (el.shadowRoot) yield* ourIcons(el.shadowRoot);
  }
}

/**
 * Register the `shelly-elevate:` icons from the panel too. The standalone icon script is only
 * loaded on page load, so right after adding the integration the sidebar would show no icon.
 * Icons that ha-icon already gave up on (unknown prefix at first render) are re-rendered.
 */
export const registerIcons = (): void => {
  const w = window as unknown as { customIcons?: Record<string, unknown> };
  w.customIcons = w.customIcons ?? {};
  w.customIcons[PREFIX] ??= {
    getIcon: async () => ({ path: mdiShellyElevateDisplay, viewBox: "0 0 24 24" }),
    getIconList: async () => [{ name: "display" }],
  };
  void (async () => {
    for (const el of ourIcons(document)) {
      if (!el._legacy) continue;
      const icon = el.icon;
      el._legacy = false;
      el.icon = undefined;
      await el.updateComplete;
      el.icon = icon;
    }
  })();
};
