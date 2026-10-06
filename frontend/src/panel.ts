/**
 * Shelly Elevate sidebar panel (`shelly-elevate-panel`), registered by panel.py with
 * embed_iframe=False. Home Assistant sets `hass`, `narrow`, `route` and `panel`.
 *
 * The panel is built from Home Assistant's own components (see ha.ts) so it looks like a
 * built-in config page: `hass-tabs-subpage` chrome, `ha-card`s, `ha-dialog`s, HA toasts.
 * It owns the display list and the confirm dialog; the tabs talk to it through the events
 * declared in ui.ts.
 */
import { LitElement, css, html, nothing, type PropertyValues } from "lit";
import {
  mdiBackupRestore,
  mdiClose,
  mdiCogs,
  mdiDownloadCircleOutline,
  mdiTune,
} from "@mdi/js";
import { mdiShellyElevateDisplay } from "./icons";
import { type DeviceSummary, ElevateApi, errorMessage, isLoaded } from "./api";
import { CORE_ELEMENTS, type HomeAssistant, type PanelInfo, type Route, loadHaElements, navigate, onDialogClosed } from "./ha";
import type { PageContext, PageNavigation } from "./page";
import { dialogStyles, sharedStyles } from "./styles";
import { type ConfirmDetail, type RevertTarget, type TabId, confirmDialog, define, plural, setEventRoot } from "./ui";
import type { SeRevertDialog } from "./components/revert-dialog";
import "./components/revert-dialog";
import "./tabs/displays";
import "./tabs/install";
import "./tabs/settings";
import "./tabs/profiles";
import "./tabs/backups";

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: "displays", label: "Displays", icon: mdiShellyElevateDisplay },
  { id: "install", label: "Install", icon: mdiDownloadCircleOutline },
  { id: "settings", label: "Settings", icon: mdiTune },
  { id: "profiles", label: "Profiles", icon: mdiCogs },
  { id: "backups", label: "Backups", icon: mdiBackupRestore },
];

class ShellyElevatePanel extends LitElement {
  static properties = {
    hass: { attribute: false },
    narrow: { type: Boolean, reflect: true },
    route: { attribute: false },
    panel: { attribute: false },
    _tab: { state: true },
    _devices: { state: true },
    _devicesError: { state: true },
    _loadingDevices: { state: true },
    _entryId: { state: true },
    _confirm: { state: true },
    _confirmOpen: { state: true },
    _ready: { state: true },
    _missing: { state: true },
    _revertUsed: { state: true },
  };

  declare hass: HomeAssistant;
  declare narrow: boolean;
  declare route?: Route;
  declare panel?: PanelInfo;
  declare _tab: TabId;
  declare _devices: DeviceSummary[];
  declare _devicesError: string;
  declare _loadingDevices: boolean;
  /** Display selected in Settings/Backups (shared so switching tabs keeps it). */
  declare _entryId: string;
  declare _confirm: ConfirmDetail | null;
  declare _confirmOpen: boolean;
  declare _ready: boolean;
  declare _missing: string[];
  /** The revert dialog is rendered once it was first opened. */
  declare _revertUsed: boolean;

  private readonly _api = new ElevateApi(() => this.hass);
  /** The install tab stays mounted once opened so a running installation survives tab switches. */
  private _installVisited = false;
  private _loadedOnce = false;
  private _tabsCache: { prefix: string; tabs: PageNavigation[] } | null = null;
  /** Unsaved changes of the Settings tab (number of changed settings, display name). */
  private _unsaved: { count: number; name: string } | null = null;

  constructor() {
    super();
    this.narrow = false;
    this._tab = "displays";
    this._devices = [];
    this._devicesError = "";
    this._loadingDevices = false;
    this._entryId = "";
    this._confirm = null;
    this._confirmOpen = false;
    this._ready = false;
    this._missing = [];
    this._revertUsed = false;
    this.addEventListener("se-revert", (ev) => {
      ev.stopPropagation();
      this._openRevert(ev.detail);
    });
    this.addEventListener("se-confirm", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      // A newer request replaces an open one (cancelled).
      this._confirm?.resolve(false);
      this._confirm = ev.detail;
      this._confirmOpen = true;
    });
    this.addEventListener("se-refresh-devices", () => this._loadDevices());
    this.addEventListener("se-open-tab", async (ev) => {
      const { tab, entryId } = ev.detail;
      if (tab !== this._tab && !(await this._confirmLeave())) return;
      if (entryId) this._entryId = entryId;
      this._setTab(tab);
    });
    this.addEventListener("se-entry-selected", (ev) => {
      this._entryId = ev.detail.entryId;
    });
    this.addEventListener("se-unsaved", (ev) => {
      this._unsaved = ev.detail;
    });
    // Links inside the panel (the tabs of the app bar) ask before unsaved settings are dropped,
    // like HA's own editors do on navigation.
    this.addEventListener("click", (ev) => this._guardLink(ev), { capture: true });
  }

  private _onBeforeUnload = (ev: BeforeUnloadEvent): void => {
    if (this._unsaved) ev.preventDefault();
  };

  private _guardLink(ev: MouseEvent): void {
    if (!this._unsaved || ev.defaultPrevented || ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey) return;
    const anchor = ev.composedPath().find((n): n is HTMLAnchorElement => n instanceof HTMLAnchorElement && !!n.href);
    if (!anchor || anchor.target === "_blank") return;
    const url = new URL(anchor.href);
    if (url.origin !== location.origin || url.pathname === location.pathname) return;
    ev.preventDefault();
    ev.stopPropagation();
    this._confirmLeave().then((ok) => ok && navigate(`${url.pathname}${url.search}`));
  }

  /** Ask before unsaved settings are dropped; resolves true when there are none. */
  private async _confirmLeave(): Promise<boolean> {
    const unsaved = this._unsaved;
    if (!unsaved) return true;
    const ok = await confirmDialog(this, {
      title: "Discard unsaved changes?",
      text: `${plural(unsaved.count, "setting")} changed on ${unsaved.name} will be lost.`,
      confirmText: "Discard",
      destructive: true,
    });
    if (ok) this._unsaved = null;
    return ok;
  }

  connectedCallback(): void {
    super.connectedCallback();
    setEventRoot(this);
    window.addEventListener("beforeunload", this._onBeforeUnload);
    loadHaElements().then((missing) => {
      this._missing = missing;
      this._ready = true;
    });
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    setEventRoot(null);
    window.removeEventListener("beforeunload", this._onBeforeUnload);
  }

  private get _prefix(): string {
    return this.route?.prefix ?? `/${this.panel?.url_path ?? "shelly-elevate"}`;
  }

  protected willUpdate(changed: PropertyValues<this>): void {
    if (changed.has("route") && this.route) {
      const seg = this.route.path.replace(/^\/+/, "").split("/")[0] as TabId;
      if (TABS.some((t) => t.id === seg)) {
        // Leaving the Settings tab drops its edits (e.g. browser back).
        if (seg !== "settings") this._unsaved = null;
        this._tab = seg;
      }
      else if (!seg) {
        // Like HA's routers: redirect the bare panel URL to the default tab.
        history.replaceState(history.state, "", `${this._prefix}/${this._tab}`);
      }
    }
    if (changed.has("hass") && this.hass && !this._loadedOnce) {
      this._loadedOnce = true;
      this._loadDevices();
    }
  }

  private async _loadDevices(): Promise<void> {
    this._loadingDevices = true;
    try {
      this._devices = await this._api.devices();
      this._devicesError = "";
      const loaded = this._devices.filter(isLoaded);
      if (!loaded.some((d) => d.entry_id === this._entryId)) this._entryId = loaded[0]?.entry_id ?? "";
    } catch (err) {
      this._devicesError = errorMessage(err);
    } finally {
      this._loadingDevices = false;
    }
  }

  private async _openRevert(target: RevertTarget): Promise<void> {
    this._revertUsed = true;
    await this.updateComplete;
    this.renderRoot.querySelector<SeRevertDialog>("sep-revert-dialog")?.show(target);
  }

  private _setTab(tab: TabId): void {
    if (tab === this._tab) return;
    this._tab = tab;
    // Same as clicking the tab: HA updates `route` (no extra history entry).
    navigate(`${this._prefix}/${tab}`, true);
  }

  private _resolveConfirm(ok: boolean): void {
    const confirm = this._confirm;
    this._confirmOpen = false;
    if (confirm) {
      confirm.resolve(ok);
      // keep the content until the closing animation is done
      this._confirm = { ...confirm, resolve: () => undefined };
    }
  }

  private _confirmClosed = onDialogClosed(() => {
    this._confirm?.resolve(false);
    this._confirm = null;
    this._confirmOpen = false;
  });

  private _context(): PageContext {
    const prefix = this._prefix;
    if (this._tabsCache?.prefix !== prefix) {
      this._tabsCache = {
        prefix,
        tabs: TABS.map((t) => ({ path: `${prefix}/${t.id}`, name: t.label, iconPath: t.icon })),
      };
    }
    return {
      hass: this.hass,
      route: { prefix, path: `/${this._tab}` },
      tabs: this._tabsCache.tabs,
      narrow: this.narrow,
      version: this.panel?.config?.version,
    };
  }

  private _renderTab(page: PageContext) {
    switch (this._tab) {
      case "install":
        return nothing; // rendered persistently, see render()
      case "settings":
        return html`<sep-settings-tab
          .page=${page}
          .api=${this._api}
          .devices=${this._devices}
          .entryId=${this._entryId}
          ?narrow=${this.narrow}
        ></sep-settings-tab>`;
      case "profiles":
        return html`<sep-profiles-tab .page=${page} .api=${this._api} .devices=${this._devices} ?narrow=${this.narrow}></sep-profiles-tab>`;
      case "backups":
        return html`<sep-backups-tab
          .page=${page}
          .api=${this._api}
          .devices=${this._devices}
          .entryId=${this._entryId}
          ?narrow=${this.narrow}
        ></sep-backups-tab>`;
      default:
        return html`<sep-displays-tab
          .page=${page}
          .api=${this._api}
          .devices=${this._devices}
          .loading=${this._loadingDevices}
          .error=${this._devicesError}
          ?narrow=${this.narrow}
        ></sep-displays-tab>`;
    }
  }

  private _renderConfirm() {
    const c = this._confirm;
    if (!c) return nothing;
    return html`
      <ha-dialog
        .open=${this._confirmOpen}
        type=${c.alert ? "standard" : "alert"}
        ?prevent-scrim-close=${!c.alert}
        aria-labelledby="se-confirm-title"
        aria-describedby="se-confirm-description"
        @closed=${this._confirmClosed}
      >
        <!-- Same header as HA's own confirmation dialog (dialog-box): close button only for alerts. -->
        <ha-dialog-header slot="header">
          ${c.alert
            ? html`<ha-icon-button
                slot="navigationIcon"
                data-dialog="close"
                .label=${"Close"}
                .path=${mdiClose}
              ></ha-icon-button>`
            : nothing}
          <h1 slot="title" class="title ${c.alert ? "" : "alert"}" id="se-confirm-title">${c.title}</h1>
        </ha-dialog-header>
        <div id="se-confirm-description">
          ${c.text ? html`<p class="confirm-text">${c.text}</p>` : nothing}
          ${c.items?.length ? html`<ul class="items">${c.items.map((i) => html`<li>${i}</li>`)}</ul>` : nothing}
        </div>
        <ha-dialog-footer slot="footer">
          ${c.alert
            ? nothing
            : html`<ha-button
                slot="secondaryAction"
                appearance="plain"
                ?autofocus=${!!c.destructive}
                @click=${() => this._resolveConfirm(false)}
              >
                ${c.dismissText ?? "Cancel"}
              </ha-button>`}
          <ha-button
            slot="primaryAction"
            variant=${c.destructive ? "danger" : "brand"}
            ?autofocus=${!c.destructive}
            @click=${() => this._resolveConfirm(true)}
          >
            ${c.confirmText ?? "OK"}
          </ha-button>
        </ha-dialog-footer>
      </ha-dialog>
    `;
  }

  render() {
    if (!this.hass || !this._ready) {
      return html`<div class="loading"><ha-spinner size="large"></ha-spinner></div>`;
    }
    const missingCore = this._missing.filter((t) => (CORE_ELEMENTS as readonly string[]).includes(t));
    if (missingCore.length) {
      return html`<div class="unsupported">
        <h1>Shelly Elevate</h1>
        <p>
          This Home Assistant frontend does not provide the components the panel needs
          (${missingCore.join(", ")}). Reload the page; if this persists, update Home Assistant.
        </p>
        <button @click=${() => location.reload()}>Reload</button>
      </div>`;
    }
    if (this._tab === "install") this._installVisited = true;
    const page = this._context();
    return html`
      ${this._renderTab(page)}
      ${this._installVisited
        ? html`<sep-install-tab
            class=${this._tab === "install" ? "" : "hidden"}
            .page=${page}
            .api=${this._api}
            .devices=${this._devices}
            .active=${this._tab === "install"}
            ?narrow=${this.narrow}
          ></sep-install-tab>`
        : nothing}
      ${this._revertUsed
        ? html`<sep-revert-dialog .api=${this._api} .devices=${this._devices}></sep-revert-dialog>`
        : nothing}
      ${this._renderConfirm()}
    `;
  }

  static styles = [
    sharedStyles,
    dialogStyles,
    css`
      :host {
        display: block;
        height: 100%;
        background: var(--primary-background-color);
      }
      .loading {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
      }
      .unsupported {
        padding: var(--ha-space-6);
        max-width: 640px;
        margin: 0 auto;
      }
      /* dialog-box */
      p {
        margin: 0;
        color: var(--primary-text-color);
      }
      .confirm-text {
        white-space: pre-line;
      }
      .title {
        font-weight: inherit;
        font-size: inherit;
        margin: inherit;
      }
      .title.alert {
        padding: 0 var(--ha-space-2);
      }
      @media all and (min-width: 450px) and (min-height: 500px) {
        .title.alert {
          padding: 0 var(--ha-space-1);
        }
      }
      .items {
        margin: var(--ha-space-2) 0 0;
        padding-inline-start: var(--ha-space-5);
      }
      .items li {
        margin-bottom: var(--ha-space-1);
      }
    `,
  ];
}

define("shelly-elevate-panel", ShellyElevatePanel);

declare global {
  interface HTMLElementTagNameMap {
    "shelly-elevate-panel": ShellyElevatePanel;
  }
}
