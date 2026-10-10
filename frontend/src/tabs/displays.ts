import { LitElement, type PropertyValues, css, html, nothing } from "lit";
import {
  mdiApplicationCogOutline,
  mdiBackupRestore,
  mdiCogs,
  mdiAccountKeyOutline,
  mdiDotsVertical,
  mdiLogin,
  mdiLogout,
  mdiMenuDown,
  mdiOpenInNew,
  mdiPackageVariantClosedRemove,
  mdiPlus,
  mdiRestart,
  mdiSleep,
  mdiTune,
  mdiWeb,
  mdiWhiteBalanceSunny,
} from "@mdi/js";
import { mdiShellyElevateDisplay } from "../icons";
import { type DeviceSummary, ElevateApi, type HaLoginStatus, type Profile, deviceName, isLoaded } from "../api";
import {
  type DropdownSelectEvent,
  type FilterChangedEvent,
  brandIconUrl,
  isChecked,
  isDefined,
  loadFilterStates,
  navigate,
} from "../ha";
import { type PageContext, pageStyles, renderPage, toolbarMenu } from "../page";
import { sharedStyles } from "../styles";
import {
  confirmDialog,
  define,
  openRevert,
  openTab,
  plural,
  refreshDevices,
  stopPropagation,
  toast,
  toastError,
} from "../ui";
import type { SeApplyProfileDialog } from "../components/apply-profile-dialog";
import type { SeLoginDialog } from "../components/login-dialog";
import "../components/apply-profile-dialog";
import "../components/login-dialog";

interface BulkAction {
  action: string;
  label: string;
  icon: string;
  destructive?: boolean;
  confirm?: string;
}

const ACTIONS: BulkAction[] = [
  { action: "screen.wake", label: "Wake", icon: mdiWhiteBalanceSunny },
  { action: "screen.sleep", label: "Sleep", icon: mdiSleep },
  { action: "webview.reload", label: "Reload dashboard", icon: mdiWeb },
  {
    action: "app.restart",
    label: "Restart app",
    icon: mdiApplicationCogOutline,
    destructive: true,
    confirm: "The Shelly Elevate app restarts; the screen is blank for a few seconds.",
  },
  {
    action: "device.reboot",
    label: "Reboot",
    icon: mdiRestart,
    destructive: true,
    confirm: "The displays reboot and are offline for about a minute.",
  },
];

const LOGIN_TEXT: Record<HaLoginStatus, string> = {
  ok: "Logged in",
  pending: "Pending",
  invalid: "Refused",
  off: "Off",
  unsupported: "App too old",
  no_dashboard: "No dashboard URL",
  error: "Error",
};

const loginText = (d: DeviceSummary): string => (d.ha_login ? LOGIN_TEXT[d.ha_login] : "—");

/** Config entry states as the integrations page names them. */
const ENTRY_STATES: Record<string, string> = {
  not_loaded: "Not loaded",
  setup_error: "Failed to set up",
  setup_retry: "Failed setup, will retry",
  migration_error: "Migration error",
  failed_unload: "Failed to unload",
  setup_in_progress: "Initializing",
  unload_in_progress: "Unloading",
};

type Status = "online" | "offline" | "not_loaded";

/** Options of the "Status" filter (ha-filter-states, as on Settings → Devices). */
const STATUS_FILTER = [
  { value: "online", label: "Online" },
  { value: "offline", label: "Offline" },
  { value: "not_loaded", label: "Not loaded" },
];

const statusOf = (d: DeviceSummary): Status => (!isLoaded(d) ? "not_loaded" : d.available ? "online" : "offline");

const statusText = (d: DeviceSummary): string =>
  !isLoaded(d) ? (ENTRY_STATES[d.state ?? ""] ?? "Not loaded") : d.available ? "Online" : "Offline";

interface Row {
  entry_id: string;
  name: string;
  model: string;
  firmware: string;
  host: string;
  status: string;
  login: string;
  selectable: boolean;
  device: DeviceSummary;
}

/**
 * Fleet overview. Uses HA's `hass-tabs-subpage-data-table` (the page type of Settings → Devices):
 * search, sorting, selection mode with bulk actions in the selection bar, "Add display" FAB.
 */
export class SeDisplaysTab extends LitElement {
  static properties = {
    page: { attribute: false },
    api: { attribute: false },
    devices: { attribute: false },
    loading: { type: Boolean },
    error: {},
    narrow: { type: Boolean, reflect: true },
    _selected: { state: true },
    _busy: { state: true },
    _profiles: { state: true },
    _icon: { state: true },
    _statusFilter: { state: true },
    _filterExpanded: { state: true },
    _hasFilter: { state: true },
  };

  declare page: PageContext;
  declare api: ElevateApi;
  declare devices: DeviceSummary[];
  declare loading: boolean;
  declare error: string;
  declare narrow: boolean;
  declare _selected: string[];
  declare _busy: string;
  declare _profiles: Profile[];
  /** Brand icon of the integration (like the device list), "" until loaded / unavailable. */
  declare _icon: string;
  /** Statuses selected in the filter pane (empty: all). */
  declare _statusFilter: string[];
  declare _filterExpanded: boolean;
  /** `ha-filter-states` is available (loaded from the devices dashboard chunk). */
  declare _hasFilter: boolean;
  private _iconRequested = false;

  constructor() {
    super();
    this.devices = [];
    this.loading = false;
    this.error = "";
    this.narrow = false;
    this._selected = [];
    this._busy = "";
    this._profiles = [];
    this._icon = "";
    this._statusFilter = [];
    this._filterExpanded = true;
    this._hasFilter = isDefined("ha-filter-states");
    if (!this._hasFilter) loadFilterStates().then((ok) => (this._hasFilter = ok));
  }

  protected willUpdate(changed: PropertyValues<this>): void {
    if (this.page && !this._iconRequested) {
      this._iconRequested = true;
      brandIconUrl(this.page.hass, "shellyelevateintegration").then((url) => (this._icon = url));
    }
    if (changed.has("devices")) {
      // Drop selections of displays that disappeared / were unloaded.
      const valid = new Set(this.devices.filter(isLoaded).map((d) => d.entry_id));
      const next = this._selected.filter((id) => valid.has(id));
      if (next.length !== this._selected.length) this._selected = next;
    }
  }

  private async _run(item: BulkAction): Promise<void> {
    const ids = [...this._selected];
    if (!ids.length) return;
    if (item.destructive || ids.length > 1) {
      const ok = await confirmDialog(this, {
        title: `${item.label} ${plural(ids.length, "display")}?`,
        text: item.confirm,
        items: ids.map((id) => deviceName(this.devices, id)),
        confirmText: item.label,
        destructive: item.destructive,
      });
      if (!ok) return;
    }
    this._busy = item.action;
    try {
      const results = await this.api.command(ids, item.action);
      const failed = Object.entries(results).filter(([, r]) => !r.ok);
      if (failed.length) {
        toast(
          this,
          `${item.label}: ${ids.length - failed.length} succeeded, ${failed.length} failed`,
          failed.length === ids.length ? "error" : "warning",
          failed.map(([id, r]) => `${deviceName(this.devices, id)}: ${r.error ?? "failed"}`),
        );
      } else {
        toast(this, `${item.label}: sent to ${plural(ids.length, "display")}`, "success");
      }
    } catch (err) {
      toastError(this, `${item.label} failed`, err);
    } finally {
      this._busy = "";
    }
  }

  private async _applyProfile(): Promise<void> {
    this._busy = "profile";
    try {
      this._profiles = (await this.api.profilesList()).profiles;
    } catch (err) {
      toastError(this, "Could not load profiles", err);
      return;
    } finally {
      this._busy = "";
    }
    if (!this._profiles.length) {
      toast(this, "There are no profiles yet. Create one in the Profiles tab.", "warning");
      return;
    }
    await this.updateComplete;
    this.renderRoot.querySelector<SeApplyProfileDialog>("sep-apply-profile-dialog")?.show(undefined, [...this._selected]);
  }

  /** Log the dashboards of the selected displays in or out of Home Assistant. */
  private async _login(login: boolean): Promise<void> {
    const ids = [...this._selected];
    if (!ids.length) return;
    const label = login ? "Log in to Home Assistant" : "Log out of Home Assistant";
    if (!login) {
      const ok = await confirmDialog(this, {
        title: `Log ${plural(ids.length, "dashboard")} out?`,
        text: "The displays show the login page and are no longer logged in by themselves.",
        items: ids.map((id) => deviceName(this.devices, id)),
        confirmText: "Log out",
        destructive: true,
      });
      if (!ok) return;
    }
    this._busy = login ? "login" : "logout";
    try {
      const results = await this.api.haLogin(ids, login);
      const failed = Object.entries(results).filter(([, r]) => !r.ok);
      if (failed.length) {
        toast(
          this,
          `${label}: ${ids.length - failed.length} succeeded, ${failed.length} failed`,
          failed.length === ids.length ? "error" : "warning",
          failed.map(
            ([id, r]) => `${deviceName(this.devices, id)}: ${r.error ?? (r.status ? LOGIN_TEXT[r.status] : "failed")}`,
          ),
        );
      } else {
        toast(this, `${label}: done on ${plural(ids.length, "display")}`, "success");
      }
    } catch (err) {
      toastError(this, `${label} failed`, err);
    } finally {
      this._busy = "";
      refreshDevices(this);
    }
  }

  private _onBulkSelect(ev: DropdownSelectEvent): void {
    const value = ev.detail.item.value;
    const action = ACTIONS.find((a) => a.action === value);
    if (action) this._run(action);
    else if (value === "profile") this._applyProfile();
    else if (value === "login") this._login(true);
    else if (value === "logout") this._login(false);
  }

  private _menu() {
    return {
      items: html`<ha-dropdown-item value="ha_login">
        <ha-svg-icon slot="icon" .path=${mdiAccountKeyOutline}></ha-svg-icon>
        Dashboard login…
      </ha-dropdown-item>`,
      onSelect: (value: string) => {
        if (value === "ha_login") this.renderRoot.querySelector<SeLoginDialog>("sep-login-dialog")?.show();
      },
    };
  }

  private _onRowMenu(d: DeviceSummary, ev: DropdownSelectEvent): void {
    const value = ev.detail.item.value;
    if (value === "device" && d.device_id) navigate(`/config/devices/device/${d.device_id}`);
    else if (value === "settings" || value === "backups") openTab(this, value, d.entry_id);
    else if (value === "revert" && d.host) openRevert(this, { host: d.host, entryId: d.entry_id, name: d.name });
  }

  // ------------------------------------------------------------------ rendering

  /**
   * Status cell: plain text like the other columns (offline in the error color, as the entities
   * table colors unavailable entities), plus HA labels (`ha-label dense`, as the labels column).
   * The cell is rendered inside ha-data-table's shadow root, so styles are inline.
   */
  private _status(d: DeviceSummary) {
    const text = statusText(d);
    const color = isLoaded(d) && !d.available ? "color:var(--error-color)" : "";
    const labels = [
      d.legacy ? html`<ha-label dense description="Pre-v1 app with the legacy HTTP API">Legacy</ha-label>` : nothing,
      d.adb ? html`<ha-label dense description="ADB access available (updates, rescue)">ADB</ha-label>` : nothing,
    ];
    if (!d.legacy && !d.adb) return html`<span style=${color}>${text}</span>`;
    return html`<div style="display:flex;flex-wrap:wrap;align-items:center;gap:4px">
      <span style=${color}>${text}</span>${labels}
    </div>`;
  }

  private _rowMenu(d: DeviceSummary) {
    const loaded = isLoaded(d);
    return html`
      <ha-dropdown placement="bottom-end" @click=${stopPropagation} @wa-select=${(ev: DropdownSelectEvent) => this._onRowMenu(d, ev)}>
        <ha-icon-button slot="trigger" .label=${"Actions"} .path=${mdiDotsVertical}></ha-icon-button>
        <ha-dropdown-item value="settings" .disabled=${!loaded}>
          <ha-svg-icon slot="icon" .path=${mdiTune}></ha-svg-icon>
          Settings
        </ha-dropdown-item>
        <ha-dropdown-item value="backups" .disabled=${!loaded}>
          <ha-svg-icon slot="icon" .path=${mdiBackupRestore}></ha-svg-icon>
          Backups
        </ha-dropdown-item>
        <ha-dropdown-item value="device" .disabled=${!d.device_id}>
          <ha-svg-icon slot="icon" .path=${mdiOpenInNew}></ha-svg-icon>
          Device page
        </ha-dropdown-item>
        <wa-divider></wa-divider>
        <ha-dropdown-item value="revert" variant="danger" .disabled=${!d.host}>
          <ha-svg-icon slot="icon" .path=${mdiPackageVariantClosedRemove}></ha-svg-icon>
          Revert to stock…
        </ha-dropdown-item>
      </ha-dropdown>
    `;
  }

  private _columns() {
    return {
      icon: {
        title: "",
        type: "icon",
        showNarrow: true,
        template: () =>
          this._icon
            ? html`<img alt="" crossorigin="anonymous" referrerpolicy="no-referrer" src=${this._icon} />`
            : html`<ha-svg-icon .path=${mdiShellyElevateDisplay}></ha-svg-icon>`,
      },
      name: {
        title: "Name",
        main: true,
        sortable: true,
        filterable: true,
        direction: "asc",
        grows: true,
        flex: 2,
        minWidth: "150px",
      },
      model: { title: "Model", sortable: true, filterable: true, groupable: true, minWidth: "120px" },
      firmware: { title: "Firmware version", sortable: true, filterable: true, minWidth: "120px" },
      host: { title: "IP address", sortable: true, filterable: true, minWidth: "120px" },
      status: {
        title: "Status",
        sortable: true,
        groupable: true,
        showNarrow: true,
        minWidth: "120px",
        template: (row: Row) => this._status(row.device),
      },
      login: { title: "Dashboard login", sortable: true, groupable: true, minWidth: "120px" },
      actions: {
        title: "",
        type: "overflow-menu",
        showNarrow: true,
        template: (row: Row) => this._rowMenu(row.device),
      },
    };
  }

  private _rows(): Row[] {
    const filter = this._statusFilter;
    const devices = filter.length ? this.devices.filter((d) => filter.includes(statusOf(d))) : this.devices;
    return devices.map((d) => ({
      entry_id: d.entry_id,
      name: d.name,
      model: isLoaded(d) ? (d.model ?? "Wall Display") : "—",
      firmware: d.fw_version ?? "—",
      host: d.host ?? "—",
      status: statusText(d),
      login: loginText(d),
      selectable: isLoaded(d),
      device: d,
    }));
  }

  /** Bulk actions in the selection bar: assist-chip dropdowns, like Settings → Devices. */
  private _selectionBar() {
    const busy = !!this._busy;
    const chip = (label: string) => html`<ha-assist-chip slot="trigger" .label=${label} ?disabled=${busy}>
      <ha-svg-icon slot="trailing-icon" .path=${mdiMenuDown}></ha-svg-icon>
    </ha-assist-chip>`;
    const commands = ACTIONS.map(
      (a) => html`<ha-dropdown-item value=${a.action} variant=${a.destructive ? "danger" : "default"}>
        <ha-svg-icon slot="icon" .path=${a.icon}></ha-svg-icon>${a.label}
      </ha-dropdown-item>`,
    );
    const profile = html`<ha-dropdown-item value="profile">
      <ha-svg-icon slot="icon" .path=${mdiCogs}></ha-svg-icon>Apply profile…
    </ha-dropdown-item>`;
    const login = html`<ha-dropdown-item value="login">
        <ha-svg-icon slot="icon" .path=${mdiLogin}></ha-svg-icon>Log in to Home Assistant
      </ha-dropdown-item>
      <ha-dropdown-item value="logout" variant="danger">
        <ha-svg-icon slot="icon" .path=${mdiLogout}></ha-svg-icon>Log out of Home Assistant
      </ha-dropdown-item>`;
    if (this.narrow) {
      return html`<ha-dropdown slot="selection-bar" @wa-select=${this._onBulkSelect}>
        ${chip("Actions")} ${commands}
        <wa-divider></wa-divider>
        ${profile}
        <wa-divider></wa-divider>
        ${login}
      </ha-dropdown>`;
    }
    return html`
      <ha-dropdown slot="selection-bar" @wa-select=${this._onBulkSelect}>${chip("Send command")} ${commands}</ha-dropdown>
      <ha-dropdown slot="selection-bar" @wa-select=${this._onBulkSelect}>
        <ha-icon-button slot="trigger" .label=${"More actions"} .path=${mdiDotsVertical} ?disabled=${busy}></ha-icon-button>
        ${profile}
        <wa-divider></wa-divider>
        ${login}
      </ha-dropdown>
    `;
  }

  /** Filter pane of the data table page: a "Status" filter like the one on Settings → Devices. */
  private _filterPane() {
    if (!this._hasFilter) return nothing;
    return html`<ha-filter-states
      slot="filter-pane"
      label="Status"
      .states=${STATUS_FILTER}
      .value=${this._statusFilter}
      .narrow=${this.narrow}
      .expanded=${this._filterExpanded}
      @expanded-changed=${(ev: CustomEvent<{ expanded: boolean }>) => (this._filterExpanded = ev.detail.expanded)}
      @data-table-filter-changed=${(ev: FilterChangedEvent) => (this._statusFilter = ev.detail.value ?? [])}
    ></ha-filter-states>`;
  }

  private _fab() {
    return html`<ha-button slot="fab" size="l" @click=${() => openTab(this, "install")}>
      <ha-svg-icon slot="start" .path=${mdiPlus}></ha-svg-icon>Add display
    </ha-button>`;
  }

  /** Same markup as the empty state of the automation list. */
  private _empty() {
    return html`<div class="empty" slot="empty">
      <ha-svg-icon .path=${mdiShellyElevateDisplay}></ha-svg-icon>
      <h1>Start managing your displays</h1>
      <p>Install Shelly Elevate on a Shelly Wall Display. It then shows up here.</p>
      <ha-button appearance="plain" size="s" @click=${() => openTab(this, "install")}>Install a display</ha-button>
    </div>`;
  }

  /** Card list for frontends without hass-tabs-subpage-data-table. */
  private _renderFallback() {
    const loaded = this.devices.filter(isLoaded);
    const all = loaded.length > 0 && loaded.every((d) => this._selected.includes(d.entry_id));
    const content = html`
      <div class="content">
        ${this.error ? html`<ha-alert alert-type="error">${this.error}</ha-alert>` : nothing}
        <ha-card>
          <h1 class="card-header">Displays</h1>
          <div class="header-actions">
            <ha-checkbox
              .checked=${all}
              .indeterminate=${!all && this._selected.length > 0}
              ?disabled=${!loaded.length}
              @change=${(e: Event) => (this._selected = isChecked(e) ? loaded.map((d) => d.entry_id) : [])}
              >All</ha-checkbox
            >
          </div>
          ${this.devices.length
            ? html`<ha-list-base>
                ${this.devices.map(
                  (d) => html`<ha-list-item-base>
                    <ha-checkbox
                      slot="start"
                      ?disabled=${!isLoaded(d)}
                      .checked=${this._selected.includes(d.entry_id)}
                      @change=${(e: Event) => {
                        this._selected = isChecked(e)
                          ? [...this._selected, d.entry_id]
                          : this._selected.filter((id) => id !== d.entry_id);
                      }}
                    ></ha-checkbox>
                    <span slot="headline">${d.name}</span>
                    <span slot="supporting-text">${d.model ?? ""} · ${d.fw_version ?? "–"} · ${d.host ?? "–"}</span>
                    <span slot="end" style="display:flex;align-items:center">${this._status(d)}${this._rowMenu(d)}</span>
                  </ha-list-item-base>`,
                )}
              </ha-list-base>`
            : this._empty()}
          ${this._selected.length
            ? html`<div class="card-actions">${this._selectionBar()}</div>`
            : nothing}
        </ha-card>
      </div>
    `;
    return renderPage(this, this.page, content, this._fab(), this._menu());
  }

  render() {
    if (!this.page) return nothing;
    const dialog = html`<sep-apply-profile-dialog
        .api=${this.api}
        .devices=${this.devices}
        .profiles=${this._profiles}
      ></sep-apply-profile-dialog>
      <sep-login-dialog .api=${this.api} @saved=${() => refreshDevices(this)}></sep-login-dialog>`;
    if (!isDefined("hass-tabs-subpage-data-table")) return html`${this._renderFallback()}${dialog}`;
    return html`
      <hass-tabs-subpage-data-table
        class=${this.narrow ? "narrow" : ""}
        main-page
        has-fab
        clickable
        selectable
        id="entry_id"
        .hass=${this.page.hass}
        .narrow=${this.narrow}
        .route=${this.page.route}
        .tabs=${this.page.tabs}
        .columns=${this._columns()}
        .data=${this._rows()}
        .loading=${this.loading && !this.devices.length}
        .loadError=${this.error || undefined}
        .empty=${!this.devices.length && !this.loading && !this.error}
        .selected=${this._selected.length}
        .noDataText=${"No displays"}
        .searchLabel=${`Search ${plural(this.devices.length, "display")}`}
        .initialSorting=${{ column: "name", direction: "asc" }}
        @selection-changed=${(ev: CustomEvent<{ value: string[] }>) => {
          if (Array.isArray(ev.detail?.value)) this._selected = ev.detail.value;
        }}
        ?has-filters=${this._hasFilter}
        .filters=${this._statusFilter.length ? 1 : 0}
        @clear-filter=${() => (this._statusFilter = [])}
        @row-click=${(ev: CustomEvent<{ id: string }>) => {
          const d = this.devices.find((x) => x.entry_id === ev.detail.id);
          if (!d) return;
          // a display that is not set up: its error is on the integration page
          if (isLoaded(d)) openTab(this, "settings", d.entry_id);
          else navigate("/config/integrations/integration/shellyelevateintegration");
        }}
      >
        ${toolbarMenu(this, this._menu())} ${this._filterPane()} ${this._selectionBar()} ${this.devices.length ? nothing : this._empty()}
        ${this._fab()}
      </hass-tabs-subpage-data-table>
      ${dialog}
    `;
  }

  static styles = [
    sharedStyles,
    pageStyles,
    css`
      /* as ha-config-devices-dashboard / ha-automation-picker */
      hass-tabs-subpage-data-table {
        --data-table-row-height: 60px;
      }
      hass-tabs-subpage-data-table.narrow {
        --data-table-row-height: 72px;
      }
      .empty {
        --mdc-icon-size: 80px;
        max-width: 500px;
      }
      .empty ha-button {
        --mdc-icon-size: 24px;
      }
      .empty h1 {
        font-size: var(--ha-font-size-3xl);
      }
      ha-assist-chip {
        --ha-assist-chip-container-shape: 10px;
      }
      ha-dropdown ha-assist-chip {
        --md-assist-chip-trailing-space: 8px;
      }
    `,
  ];
}

define("sep-displays-tab", SeDisplaysTab);

declare global {
  interface HTMLElementTagNameMap {
    "sep-displays-tab": SeDisplaysTab;
  }
}
