/**
 * Page chrome shared by all tabs: Home Assistant's `hass-tabs-subpage` (top app bar with the
 * sidebar toggle, tabs in the bar on wide screens and as bottom bar on phones, FAB area) –
 * the same element the config pages use. A minimal look-alike is rendered if it is missing.
 * Also building blocks used by several tabs.
 */
import { css, html, nothing, type TemplateResult } from "lit";
import { mdiChevronDown, mdiCogOutline, mdiDotsVertical, mdiRefresh } from "@mdi/js";
import { mdiShellyElevateDisplay } from "./icons";
import { type DeviceSummary, isLoaded } from "./api";
import {
  type DropdownSelectEvent,
  type HomeAssistant,
  type PickerItem,
  type Route,
  type ValueChangedEvent,
  isDefined,
  navigate,
} from "./ha";
import { openTab, plural, refreshDevices } from "./ui";

export interface PageNavigation {
  path: string;
  name: string;
  iconPath: string;
}

export interface PageContext {
  hass: HomeAssistant;
  /** Route of the active tab: `{prefix: "/shelly-elevate", path: "/settings"}`. */
  route: Route;
  tabs: PageNavigation[];
  narrow: boolean;
  version?: string;
}

/** Page specific entries of the toolbar menu (listed before the common ones). */
export interface PageMenu {
  items?: TemplateResult;
  onSelect?: (value: string) => void;
  /**
   * "Reload" reloads the display list and calls this for the page's own data (one entry
   * instead of a second "Reload …" item). Return false to cancel (e.g. unsaved changes kept).
   */
  onReload?: () => Promise<boolean> | boolean | void;
  /** Shown in the app bar before the menu (the display picker of the per-display tabs). */
  picker?: TemplateResult;
}

const onMenuSelect = async (host: HTMLElement, ev: DropdownSelectEvent, menu?: PageMenu): Promise<void> => {
  const value = ev.detail.item.value;
  if (value === "reload") {
    if ((await menu?.onReload?.()) !== false) refreshDevices(host);
  } else if (value === "integration") navigate("/config/integrations/integration/shellyelevateintegration");
  else menu?.onSelect?.(value);
};

/**
 * App bar content: the overflow menu (same markup as the "⋮" menu of HA config pages), with the
 * page's picker in front of it. `#toolbar-icon` of hass-tabs-subpage is not a flex box, so both
 * share one slotted element.
 */
export const toolbarMenu = (host: HTMLElement, menu?: PageMenu) => {
  const dropdown = html`<ha-dropdown
    slot=${menu?.picker ? nothing : "toolbar-icon"}
    placement="bottom-end"
    @wa-select=${(ev: DropdownSelectEvent) => onMenuSelect(host, ev, menu)}
  >
    <ha-icon-button slot="trigger" .label=${"Menu"} .path=${mdiDotsVertical}></ha-icon-button>
    ${menu?.items ? html`${menu.items}<wa-divider></wa-divider>` : nothing}
    <ha-dropdown-item value="reload">
      <ha-svg-icon slot="icon" .path=${mdiRefresh}></ha-svg-icon>
      Reload
    </ha-dropdown-item>
    <ha-dropdown-item value="integration">
      <ha-svg-icon slot="icon" .path=${mdiCogOutline}></ha-svg-icon>
      Integration settings
    </ha-dropdown-item>
  </ha-dropdown>`;
  return menu?.picker ? html`<div slot="toolbar-icon" class="toolbar-icons">${menu.picker}${dropdown}</div>` : dropdown;
};

/** Render a tab page. `fab` content must carry `slot="fab"` on its top-level elements. */
export const renderPage = (
  host: HTMLElement,
  ctx: PageContext,
  content: TemplateResult | typeof nothing,
  fab: TemplateResult | typeof nothing = nothing,
  menu?: PageMenu,
) => {
  const hasFab = fab !== nothing;
  if (isDefined("hass-tabs-subpage")) {
    return html`
      <hass-tabs-subpage main-page .hass=${ctx.hass} .route=${ctx.route} .tabs=${ctx.tabs} ?has-fab=${hasFab}>
        <span slot="header" class="header">Shelly Elevate</span>
        ${toolbarMenu(host, menu)}
        ${content} ${fab}
      </hass-tabs-subpage>
    `;
  }
  // Fallback: look-alike of hass-tabs-subpage.
  const current = `${ctx.route.prefix}${ctx.route.path}`;
  return html`
    <div class="fb-page">
      <div class="fb-toolbar">
        <ha-menu-button .hass=${ctx.hass} .narrow=${ctx.narrow}></ha-menu-button>
        <div class="fb-title">Shelly Elevate</div>
        ${toolbarMenu(host, menu)}
      </div>
      <nav class="fb-tabs">
        ${ctx.tabs.map(
          (t) => html`<a
            href=${t.path}
            class=${t.path === current ? "active" : ""}
            @click=${(ev: MouseEvent) => {
              ev.preventDefault();
              navigate(t.path, true);
            }}
            ><ha-svg-icon .path=${t.iconPath}></ha-svg-icon><span>${t.name}</span></a
          >`,
        )}
      </nav>
      <div class="fb-content">${content}</div>
      ${hasFab ? html`<div class="fb-fab">${fab}</div>` : nothing}
    </div>
  `;
};

/** Alert shown by the per-display tabs when no display is loaded. */
export const noDisplaysCard = (host: HTMLElement, devices: DeviceSummary[]) =>
  devices.length
    ? html`<ha-alert alert-type="warning" title="No display is loaded">
        ${plural(devices.length, "display")} could not be set up. Open the integration page to see why.
        <ha-button
          slot="action"
          appearance="plain"
          @click=${() => navigate("/config/integrations/integration/shellyelevateintegration")}
          >Open</ha-button
        >
      </ha-alert>`
    : html`<ha-alert alert-type="info" title="No display yet">
        Install Shelly Elevate on a Shelly Wall Display to manage it here.
        <ha-button slot="action" appearance="plain" @click=${() => openTab(host, "install")}>Install</ha-button>
      </ha-alert>`;

/** Rows of the display picker (same as the provider rows of the Logs picker). */
const pickerRow = (item: PickerItem) => html`<ha-combo-box-item type="button" compact>
  ${item.icon_path ? html`<ha-svg-icon slot="start" .path=${item.icon_path}></ha-svg-icon>` : nothing}
  <span slot="headline">${item.primary}</span>
  ${item.secondary ? html`<span slot="supporting-text">${item.secondary}</span>` : nothing}
</ha-combo-box-item>`;

/** ha-generic-picker wants a stable `getItems` (it is called on every render). */
const pickerItems = new WeakMap<DeviceSummary[], () => PickerItem[]>();
const pickerItemsFor = (devices: DeviceSummary[]): (() => PickerItem[]) => {
  let fn = pickerItems.get(devices);
  if (!fn) {
    const items = devices.filter(isLoaded).map((d) => ({
      id: d.entry_id,
      primary: d.name,
      secondary: d.available ? undefined : "Offline",
      icon_path: mdiShellyElevateDisplay,
    }));
    fn = () => items;
    pickerItems.set(devices, fn);
  }
  return fn;
};

/**
 * Display picker of the per-display tabs (loaded displays only), in the app bar like the log
 * provider picker of Settings → System → Logs: `ha-generic-picker` with a filled button as its
 * field (a searchable popover, a bottom sheet on phones).
 */
export const displayPicker = (
  hass: HomeAssistant,
  devices: DeviceSummary[],
  entryId: string,
  onSelect: (entryId: string) => void,
) => {
  const loaded = devices.filter(isLoaded);
  const current = loaded.find((d) => d.entry_id === entryId);
  const button = (onClick?: (ev: Event) => void) => html`<ha-button
    slot=${onClick ? "field" : "trigger"}
    appearance="filled"
    .disabled=${!loaded.length}
    @click=${onClick}
  >
    <ha-svg-icon slot="start" .path=${mdiShellyElevateDisplay}></ha-svg-icon>
    ${current?.name ?? "Display"}
    <ha-svg-icon slot="end" .path=${mdiChevronDown}></ha-svg-icon>
  </ha-button>`;
  if (isDefined("ha-generic-picker")) {
    return html`<ha-generic-picker
      class="display-picker"
      .hass=${hass}
      .getItems=${pickerItemsFor(devices)}
      .value=${entryId}
      .rowRenderer=${pickerRow}
      label="Display"
      search-label="Search displays"
      @value-changed=${(ev: ValueChangedEvent<string>) => {
        ev.stopPropagation();
        if (ev.detail?.value) onSelect(ev.detail.value);
      }}
    >
      ${button((ev) => {
        ev.stopPropagation();
        ((ev.currentTarget as HTMLElement).parentElement as HTMLElement & { open(): void }).open();
      })}
    </ha-generic-picker>`;
  }
  // Fallback: a menu with the displays.
  return html`<ha-dropdown
    class="display-picker"
    placement="bottom-end"
    @wa-select=${(ev: DropdownSelectEvent) => {
      ev.stopPropagation();
      onSelect(ev.detail.item.value);
    }}
  >
    ${button()}
    ${loaded.map(
      (d) => html`<ha-dropdown-item value=${d.entry_id} .selected=${d.entry_id === entryId}>
        <ha-svg-icon slot="icon" .path=${mdiShellyElevateDisplay}></ha-svg-icon>
        ${d.name}${d.available ? nothing : html` (offline)`}
      </ha-dropdown-item>`,
    )}
  </ha-dropdown>`;
};

export const pageStyles = css`
  :host {
    display: block;
    height: 100%;
  }
  /* the title keeps to one line when the app bar also holds the display picker (narrow) */
  .header {
    display: block;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .toolbar-icons {
    display: flex;
    align-items: center;
    gap: var(--ha-space-1);
    min-width: 0;
  }
  /* ha-config-logs */
  .display-picker {
    --md-list-item-leading-icon-color: var(--ha-color-primary-50);
    --mdc-icon-size: var(--ha-space-6);
    min-width: 0;
  }
  :host([narrow]) .display-picker ha-svg-icon[slot="start"] {
    display: none;
  }
  @media all and (max-width: 870px) {
    .display-picker {
      max-width: max(30%, 180px);
    }
    .display-picker ha-button {
      max-width: 100%;
    }
    .display-picker ha-button::part(label) {
      overflow: hidden;
      white-space: nowrap;
    }
  }
  /* search bar below the app bar (ha-config-logs) */
  .search {
    position: sticky;
    top: 0;
    z-index: 2;
  }
  .search ha-input-search,
  .search ha-input {
    padding: var(--ha-space-3);
    background: var(--sidebar-background-color);
    border-bottom: 1px solid var(--divider-color);
  }
  .fb-page {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--primary-background-color);
  }
  .fb-toolbar {
    display: flex;
    align-items: center;
    gap: var(--ha-space-2);
    height: calc(var(--header-height, 56px) + var(--safe-area-inset-top, 0px));
    padding: var(--safe-area-inset-top, 0px) 12px 0;
    background: var(--sidebar-background-color);
    color: var(--sidebar-text-color);
    border-bottom: 1px solid var(--divider-color);
    font-size: var(--ha-font-size-xl);
  }
  .fb-title {
    flex: 1;
    margin-inline-start: var(--ha-space-4);
  }
  .fb-tabs {
    display: flex;
    overflow-x: auto;
    background: var(--sidebar-background-color);
    border-bottom: 1px solid var(--divider-color);
  }
  .fb-tabs a {
    display: inline-flex;
    align-items: center;
    gap: var(--ha-space-2);
    padding: 0 var(--ha-space-4);
    height: 48px;
    color: var(--sidebar-text-color);
    text-decoration: none;
    border-bottom: 2px solid transparent;
    white-space: nowrap;
  }
  .fb-tabs a.active {
    color: var(--primary-color);
    border-bottom-color: var(--primary-color);
  }
  .fb-content {
    flex: 1;
    overflow: auto;
  }
  .fb-fab {
    position: fixed;
    right: calc(16px + var(--safe-area-inset-right, 0px));
    bottom: calc(16px + var(--safe-area-inset-bottom, 0px));
    display: flex;
    gap: var(--ha-space-2);
    z-index: 1;
  }
`;
