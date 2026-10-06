/**
 * Access to Home Assistant's own web components.
 *
 * The panel runs inside the HA frontend (embed_iframe=False) and renders HA's elements
 * (`ha-card`, `ha-button`, `hass-tabs-subpage`, ...). Most of them are lazy-loaded by HA, so
 * `loadHaElements()` makes sure they are defined before the panel renders:
 *
 * 1. nothing to do when they are already registered (the usual case: HA 2026.8 - 2026.10
 *    preload them together with the sidebar / custom panel host);
 * 2. otherwise load the config panel through `partial-panel-resolver` and a few of its
 *    sub-pages (the chunks that define the config page building blocks);
 * 3. as a last resort for `ha-form`, use `loadCardHelpers()` and load a card editor.
 *
 * Whatever is still missing afterwards is reported; the panel degrades (own toolbar instead of
 * `hass-tabs-subpage`, card list instead of the data table, native textarea instead of
 * `ha-code-editor`).
 */

/** Elements the panel cannot work without. */
export const CORE_ELEMENTS = [
  "ha-card",
  "ha-button",
  "ha-icon-button",
  "ha-svg-icon",
  "ha-switch",
  "ha-checkbox",
  "ha-input",
  "ha-select",
  "ha-dropdown",
  "ha-dropdown-item",
  "ha-alert",
  "ha-spinner",
  "ha-expansion-panel",
  "ha-settings-row",
  "ha-dialog",
  "ha-dialog-header",
  "ha-dialog-footer",
  "ha-form",
  "ha-list-base",
  "ha-list-item-base",
  "ha-list-item-button",
  "ha-label",
  "ha-menu-button",
] as const;

/** Elements with a fallback in the panel. */
const OPTIONAL_ELEMENTS = [
  "hass-tabs-subpage",
  "hass-tabs-subpage-data-table",
  "ha-input-search",
  "ha-generic-picker",
  "ha-code-editor",
  "ha-markdown",
] as const;

const ALL = [...CORE_ELEMENTS, ...OPTIONAL_ELEMENTS];

export const isDefined = (tag: string): boolean => customElements.get(tag) !== undefined;

const missing = (tags: readonly string[] = ALL): string[] => tags.filter((t) => !isDefined(t));

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Resolve when all tags are defined or after `ms`. */
const whenDefined = (tags: string[], ms: number): Promise<unknown> =>
  Promise.race([Promise.all(tags.map((t) => customElements.whenDefined(t))), sleep(ms)]);

type Routes = Record<string, { load?: () => Promise<unknown> } | undefined>;

const routesOf = (tag: string): Routes => {
  if (!isDefined(tag)) return {};
  // Router pages keep their routes in the `routerOptions` class field.
  const el = document.createElement(tag) as unknown as { routerOptions?: { routes?: Routes } };
  return el.routerOptions?.routes ?? {};
};

const loadRoutes = async (routes: Routes, names: string[]): Promise<void> => {
  await Promise.allSettled(names.map((n) => routes[n]?.load?.()));
};

/** Load the config panel and the config sub-pages that use the building blocks we need. */
const loadViaConfigPanel = async (): Promise<void> => {
  await whenDefined(["partial-panel-resolver"], 5000);
  if (!isDefined("ha-panel-config")) {
    const resolver = document.createElement("partial-panel-resolver") as unknown as {
      _getRoutes?: (panels: Record<string, { component_name: string; url_path: string }>) => { routes?: Routes };
    };
    const routes = resolver._getRoutes?.({ config: { component_name: "config", url_path: "config" } })?.routes ?? {};
    await loadRoutes(routes, ["config"]);
    await whenDefined(["ha-panel-config"], 5000);
  }
  const config = routesOf("ha-panel-config");
  // devices: data table page, integrations: tabs subpage + cards, backup: dialogs + lists,
  // automation: forms / selectors / code editor.
  await loadRoutes(config, ["devices", "integrations", "backup", "automation", "voice-assistants"]);
  await loadRoutes(routesOf("ha-config-devices"), ["dashboard"]);
  await loadRoutes(routesOf("ha-config-backup"), ["overview", "backups"]);
  await loadRoutes(routesOf("ha-config-automation"), ["dashboard", "edit"]);
  await loadRoutes(routesOf("ha-config-voice-assistants"), ["assistants"]);
};

/** `loadCardHelpers()` is provided by the Lovelace panel; card editors pull in ha-form. */
const loadViaCardHelpers = async (): Promise<void> => {
  const w = window as unknown as { loadCardHelpers?: () => Promise<{ createCardElement(c: unknown): unknown }> };
  if (!w.loadCardHelpers) return;
  const helpers = await w.loadCardHelpers();
  const card = helpers.createCardElement({ type: "entities", entities: [] }) as {
    constructor: { getConfigElement?: () => Promise<unknown> };
  };
  await card.constructor.getConfigElement?.();
};

let loading: Promise<string[]> | null = null;

/** Make sure HA's elements are defined. Resolves with the tags that are still missing. */
export const loadHaElements = (): Promise<string[]> => {
  if (!loading) {
    loading = (async () => {
      if (!missing().length) return [];
      // Elements may still be registering (the panel module can load before HA's chunks).
      await whenDefined(missing(), 1500);
      if (!missing().length) return [];
      try {
        await loadViaConfigPanel();
      } catch (err) {
        console.warn("shelly-elevate: loading the config panel failed", err);
      }
      if (missing(["ha-form"]).length) {
        try {
          await loadViaCardHelpers();
        } catch (err) {
          console.warn("shelly-elevate: loading card helpers failed", err);
        }
      }
      await whenDefined(missing(), 3000);
      const left = missing();
      if (left.length) console.warn("shelly-elevate: Home Assistant elements not available:", left.join(", "));
      return left;
    })();
  }
  return loading;
};

/**
 * `ha-progress-bar` (used by HA's update and backup upload dialogs) is only defined once one of
 * those is opened. The file selector pulls it in (ha-selector-file → ha-file-upload →
 * ha-progress-bar), so render a hidden `ha-selector` with a file selector once.
 */
export const loadProgressBar = async (hass: unknown, parent: Node): Promise<boolean> => {
  if (isDefined("ha-progress-bar")) return true;
  if (!isDefined("ha-selector")) return false;
  const holder = document.createElement("div");
  holder.style.display = "none";
  const selector = document.createElement("ha-selector") as HTMLElement & { hass?: unknown; selector?: unknown };
  selector.hass = hass;
  selector.selector = { file: { accept: ".txt" } };
  holder.appendChild(selector);
  // Inside the panel, so the selector finds HA's context providers (localize, ...).
  parent.appendChild(holder);
  try {
    await whenDefined(["ha-progress-bar"], 8000);
  } finally {
    holder.remove();
  }
  return isDefined("ha-progress-bar");
};

/**
 * `ha-filter-states` (the "Status" filter of Settings → Devices) is defined by the devices
 * dashboard chunk; load that chunk when the element is not registered yet.
 */
export const loadFilterStates = async (): Promise<boolean> => {
  if (isDefined("ha-filter-states")) return true;
  try {
    if (!isDefined("ha-config-devices")) {
      if (!isDefined("ha-panel-config")) await loadViaConfigPanel();
      await loadRoutes(routesOf("ha-panel-config"), ["devices"]);
    }
    await loadRoutes(routesOf("ha-config-devices"), ["dashboard"]);
    await whenDefined(["ha-filter-states"], 3000);
  } catch (err) {
    console.warn("shelly-elevate: loading the status filter failed", err);
  }
  return isDefined("ha-filter-states");
};

// --------------------------------------------------------------------------- HA objects

export type UnsubscribeFunc = () => Promise<void> | void;

export interface HassConnection {
  subscribeMessage<T>(
    callback: (message: T) => void,
    subscribeMessage: Record<string, unknown>,
    options?: { resubscribe?: boolean },
  ): Promise<UnsubscribeFunc>;
}

/** The subset of Home Assistant's `hass` object the panel uses. */
export interface HomeAssistant {
  callWS<T>(message: Record<string, unknown>): Promise<T>;
  connection: HassConnection;
  locale?: { language?: string };
  themes?: { darkMode?: boolean };
}

/** The `panel` property Home Assistant sets on a custom panel. */
export interface PanelInfo {
  config?: { version?: string };
  url_path?: string;
}

export interface Route {
  prefix: string;
  path: string;
}

// --------------------------------------------------------------------------- HA element events

/** `wa-select` of `ha-dropdown`. */
export type DropdownSelectEvent = CustomEvent<{ item: { value: string } }>;

/** An item of `ha-generic-picker` (`PickerComboBoxItem` of the HA frontend). */
export interface PickerItem {
  id: string;
  primary: string;
  secondary?: string;
  icon_path?: string;
}

/** `data-table-filter-changed` of the `ha-filter-*` elements. */
export type FilterChangedEvent = CustomEvent<{ value?: string[] }>;

/** `selected` of `ha-select`. */
export type SelectedEvent = CustomEvent<{ value: string }>;

/** `value-changed` of `ha-form` and `ha-code-editor`. */
export type ValueChangedEvent<T> = CustomEvent<{ value: T }>;

/** One entry of an `ha-form` schema (the subset the panel uses). */
export interface HaFormSchema {
  name: string;
  required?: boolean;
  disabled?: boolean;
  selector: Record<string, unknown>;
}

/** Value of the `ha-input` / `ha-input-search` / native input that fired `ev`. */
export const inputValue = (ev: Event): string => (ev.currentTarget as HTMLInputElement).value ?? "";

/** State of the `ha-checkbox` / `ha-switch` that fired `ev`. */
export const isChecked = (ev: Event): boolean => (ev.currentTarget as HTMLInputElement).checked;

/** `closed` handler for `ha-dialog` that ignores `closed` events bubbling up from nested elements. */
export const onDialogClosed =
  (fn: () => void) =>
  (ev: Event): void => {
    if (ev.target === ev.currentTarget) fn();
  };

// --------------------------------------------------------------------------- HA helpers

export const fireEvent = <T>(node: EventTarget, type: string, detail?: T): void => {
  node.dispatchEvent(new CustomEvent(type, { detail, bubbles: true, composed: true }));
};

/** Navigate inside the Home Assistant frontend without a page reload. */
export const navigate = (path: string, replace = false): void => {
  if (replace) history.replaceState(history.state, "", path);
  else history.pushState(null, "", path);
  fireEvent(window, "location-changed", { replace });
};

/** Home Assistant's own toast (snackbar). */
export const showToast = (
  el: HTMLElement,
  params: { message: string; duration?: number; dismissable?: boolean; action?: { text: string; action: () => void } },
): void => fireEvent(el, "hass-notification", params);

// --------------------------------------------------------------------------- brand images

let brandsToken: Promise<string | null> | null = null;

/**
 * URL of an integration's brand icon, as the devices page shows it (`brandsUrl()` of the HA
 * frontend: `/api/brands/integration/<domain>/[dark_]icon.png?token=…`). Resolves with "" when the
 * brands API is not available.
 */
export const brandIconUrl = async (hass: HomeAssistant, domain: string): Promise<string> => {
  if (!brandsToken) {
    brandsToken = hass
      .callWS<{ token: string }>({ type: "brands/access_token" })
      .then((r) => r.token)
      .catch(() => null);
    // The token is valid for an hour; fetch a fresh one after 30 minutes.
    setTimeout(() => (brandsToken = null), 30 * 60 * 1000);
  }
  const token = await brandsToken;
  if (!token) return "";
  const url = new URL(`/api/brands/integration/${domain}/${hass.themes?.darkMode ? "dark_" : ""}icon.png`, location.origin);
  url.searchParams.set("token", token);
  return url.toString();
};

/** Copy text to the clipboard (with the textarea fallback HA's `copyToClipboard` uses). */
export const copyToClipboard = async (text: string): Promise<void> => {
  if (navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // fall through
    }
  }
  const el = document.createElement("textarea");
  el.value = text;
  document.body.appendChild(el);
  el.select();
  document.execCommand("copy");
  el.remove();
};
