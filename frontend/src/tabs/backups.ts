import { LitElement, type PropertyValues, css, html, nothing } from "lit";
import {
  mdiBackupRestore,
  mdiCalendarSync,
  mdiDelete,
  mdiDotsVertical,
  mdiDownload,
  mdiFileCompare,
  mdiGestureTap,
  mdiPlus,
  mdiShieldRefreshOutline,
  mdiUpload,
} from "@mdi/js";
import { type Backup, type DeviceSummary, type DiffItem, ElevateApi, errorMessage, isLoaded } from "../api";
import { type DropdownSelectEvent, type SelectedEvent, inputValue, onDialogClosed } from "../ha";
import { type PageContext, type PageMenu, displayPicker, noDisplaysCard, pageStyles, renderPage } from "../page";
import { dialogStyles, sharedStyles } from "../styles";
import {
  confirmDialog,
  define,
  downloadJson,
  formatDate,
  plural,
  selectEntry,
  slug,
  stopPropagation,
  toast,
  toastError,
} from "../ui";
import "../components/diff-table";

const REASONS: Record<string, [string, string]> = {
  manual: ["Manual", mdiGestureTap],
  auto: ["Automatic", mdiCalendarSync],
  setup: ["Setup", mdiCalendarSync],
  before_restore: ["Before restore", mdiShieldRefreshOutline],
  before_profile: ["Before profile", mdiShieldRefreshOutline],
  before_update: ["Before update", mdiShieldRefreshOutline],
  import: ["Imported", mdiUpload],
};

interface DiffState {
  backup: Backup;
  /** Display id (store key) of the backup when it belongs to another display. */
  source?: string;
  diff: DiffItem[] | null;
  selected: Set<string>;
  error: string;
  restoring: boolean;
}

/** Backups of the selected display, plus restoring from backups of other (or removed) displays. */
export class SeBackupsTab extends LitElement {
  static properties = {
    page: { attribute: false },
    api: { attribute: false },
    devices: { attribute: false },
    entryId: {},
    narrow: { type: Boolean, reflect: true },
    _displayId: { state: true },
    _backups: { state: true },
    _all: { state: true },
    _loading: { state: true },
    _error: { state: true },
    _newName: { state: true },
    _createOpen: { state: true },
    _creating: { state: true },
    _source: { state: true },
    _diff: { state: true },
    _diffOpen: { state: true },
    _busyId: { state: true },
  };

  declare page: PageContext;
  declare api: ElevateApi;
  declare devices: DeviceSummary[];
  declare entryId: string;
  declare narrow: boolean;
  /** Store key of the selected display's backups. */
  declare _displayId: string;
  declare _backups: Backup[] | null;
  /** Backups of all displays, keyed by display id (store key). */
  declare _all: Record<string, Backup[]>;
  declare _loading: boolean;
  declare _error: string;
  declare _newName: string;
  declare _createOpen: boolean;
  declare _creating: boolean;
  /** Display id whose backups are listed under "Restore from another display". */
  declare _source: string;
  declare _diff: DiffState | null;
  declare _diffOpen: boolean;
  declare _busyId: string;

  /** entry id the current data belongs to */
  private _loadedFor = "";

  constructor() {
    super();
    this.devices = [];
    this.entryId = "";
    this.narrow = false;
    this._displayId = "";
    this._backups = null;
    this._all = {};
    this._loading = false;
    this._error = "";
    this._newName = "";
    this._createOpen = false;
    this._creating = false;
    this._source = "";
    this._diff = null;
    this._diffOpen = false;
    this._busyId = "";
  }

  protected willUpdate(changed: PropertyValues<this>): void {
    if ((changed.has("entryId") || changed.has("api")) && this.api && this.entryId && this.entryId !== this._loadedFor) {
      this._load();
    }
  }

  private get _device(): DeviceSummary | undefined {
    return this.devices.find((d) => d.entry_id === this.entryId);
  }

  private get _lang(): string | undefined {
    return this.page?.hass.locale?.language;
  }

  private async _load(): Promise<void> {
    const entryId = this.entryId;
    // Another display: don't show (or act on) the previous display's backups while loading.
    if (this._loadedFor !== entryId) {
      this._backups = null;
      this._displayId = "";
      this._all = {};
      this._source = "";
    }
    this._loadedFor = entryId;
    this._loading = true;
    this._error = "";
    try {
      const [mine, all] = await Promise.all([this.api.backupsList(entryId), this.api.backupsList()]);
      if (entryId !== this.entryId) return;
      const displayId = Object.keys(mine)[0] ?? "";
      this._displayId = displayId;
      this._backups = mine[displayId] ?? [];
      this._all = all;
      const others = this._otherIds;
      if (!others.includes(this._source)) this._source = others[0] ?? "";
    } catch (err) {
      if (entryId !== this.entryId) return;
      this._error = errorMessage(err);
      this._backups = null;
    } finally {
      if (entryId === this.entryId) this._loading = false;
    }
  }

  /** Display ids with backups other than the selected display, sorted by label. */
  private get _otherIds(): string[] {
    return Object.keys(this._all)
      .filter((id) => id !== this._displayId && (this._all[id]?.length ?? 0) > 0)
      .sort((a, b) => this._label(a).localeCompare(this._label(b)));
  }

  /** Name of the loaded display with this display id. */
  private _name(displayId: string): string | undefined {
    return this.devices.find((d) => isLoaded(d) && d.display_id === displayId)?.name;
  }

  private _label(displayId: string): string {
    const name = this._name(displayId);
    if (name) return name;
    const model = this._all[displayId]?.[0]?.model;
    return `${displayId}${model ? ` (${model})` : ""} – removed`;
  }

  // ------------------------------------------------------------------ actions

  private _openCreate(): void {
    this._newName = "";
    this._createOpen = true;
  }

  private async _create(): Promise<void> {
    this._creating = true;
    try {
      const backup = await this.api.backupsCreate(this.entryId, this._newName.trim() || undefined);
      toast(this, `Backup created${backup.name ? `: ${backup.name}` : ""}`, "success");
      this._creating = false;
      this._createOpen = false;
      await this._load();
    } catch (err) {
      toastError(this, "Backup failed", err);
    } finally {
      this._creating = false;
    }
  }

  private async _openDiff(backup: Backup, source?: string): Promise<void> {
    this._diff = { backup, source, diff: null, selected: new Set(), error: "", restoring: false };
    this._diffOpen = true;
    try {
      const diff = await this.api.backupsDiff(this.entryId, backup.id, source);
      if (this._diff?.backup.id !== backup.id) return;
      this._diff = { ...this._diff, diff, selected: new Set(diff.map((d) => d.key)) };
    } catch (err) {
      if (this._diff?.backup.id !== backup.id) return;
      this._diff = { ...this._diff, error: errorMessage(err) };
    }
  }

  private async _restore(): Promise<void> {
    const st = this._diff;
    if (!st?.diff) return;
    const all = st.selected.size === st.diff.length;
    const keys = all ? undefined : [...st.selected];
    const ok = await confirmDialog(this, {
      title: `Restore ${plural(st.selected.size, "setting")}?`,
      text: `${this._device?.name ?? "The display"} gets ${all ? "all changed settings" : "the selected settings"} from the backup of ${formatDate(
        st.backup.created,
        this._lang,
      )}${st.source ? ` (from ${this._label(st.source)})` : ""}.\n\nA backup of the current settings is taken first.`,
      confirmText: "Restore",
      destructive: true,
    });
    if (!ok) return;
    this._diff = { ...st, restoring: true };
    try {
      const changes = await this.api.backupsRestore(this.entryId, st.backup.id, keys, st.source);
      toast(this, `Restored ${plural(changes.length, "setting")} on ${this._device?.name ?? "the display"}`, "success");
      this._diff = { ...st, restoring: false };
      this._diffOpen = false;
      await this._load();
    } catch (err) {
      this._diff = { ...st, restoring: false, error: errorMessage(err) };
    }
  }

  private async _delete(displayId: string, backup: Backup): Promise<void> {
    const ok = await confirmDialog(this, {
      title: "Delete backup?",
      text: `The backup${backup.name ? ` “${backup.name}”` : ""} of ${this._label(displayId)} from ${formatDate(backup.created, this._lang)} will be permanently deleted.`,
      confirmText: "Delete",
      destructive: true,
    });
    if (!ok) return;
    this._busyId = backup.id;
    try {
      await this.api.backupsDelete(displayId, backup.id);
      toast(this, "Backup deleted", "success");
      await this._load();
    } catch (err) {
      toastError(this, "Delete failed", err);
    } finally {
      this._busyId = "";
    }
  }

  private _download(displayId: string, backup: Backup): void {
    const name = this._name(displayId) ?? displayId;
    downloadJson(`backup-${slug(name)}-${backup.created.slice(0, 19).replace(/[:T]/g, "-")}.json`, {
      format: "shellyelevateintegration.backup/1",
      device_id: displayId,
      device_name: name,
      ...backup,
    });
  }

  private _onMenu(displayId: string, b: Backup, source: string | undefined, ev: DropdownSelectEvent): void {
    switch (ev.detail.item.value) {
      case "restore":
        this._openDiff(b, source);
        break;
      case "download":
        this._download(displayId, b);
        break;
      case "delete":
        this._delete(displayId, b);
        break;
      default:
        break;
    }
  }

  // ------------------------------------------------------------------ rendering

  /** Backup rows: the list of ha-backup-overview-backups with an overflow menu per row (assist-pref). */
  private _renderList(displayId: string, backups: Backup[], source?: string) {
    if (!backups.length) return html`<p>No backups yet.</p>`;
    return html`
      <ha-list-base aria-label="Backups">
        ${backups.map((b) => {
          const [reason, icon] = REASONS[b.reason] ?? [b.reason, mdiBackupRestore];
          const busy = this._busyId === b.id;
          return html`
            <ha-list-item-button @click=${() => this._openDiff(b, source)}>
              <ha-svg-icon slot="start" .path=${icon}></ha-svg-icon>
              <span slot="headline">${b.name ? b.name : formatDate(b.created, this._lang)}</span>
              <span slot="supporting-text">
                ${b.name ? html`${formatDate(b.created, this._lang)} · ` : nothing}${reason} ·
                ${plural(Object.keys(b.settings ?? {}).length, "setting")}${b.fw_version ? ` · Firmware ${b.fw_version}` : ""}
              </span>
              ${busy ? html`<ha-spinner slot="end" size="small"></ha-spinner>` : nothing}
              <ha-dropdown
                slot="end"
                placement="bottom-end"
                @click=${stopPropagation}
                @wa-select=${(e: DropdownSelectEvent) => this._onMenu(displayId, b, source, e)}
              >
                <ha-icon-button slot="trigger" .label=${"Menu"} .path=${mdiDotsVertical}></ha-icon-button>
                <ha-dropdown-item value="restore">
                  <ha-svg-icon slot="icon" .path=${mdiFileCompare}></ha-svg-icon>Compare and restore
                </ha-dropdown-item>
                <ha-dropdown-item value="download">
                  <ha-svg-icon slot="icon" .path=${mdiDownload}></ha-svg-icon>Download
                </ha-dropdown-item>
                <wa-divider></wa-divider>
                <ha-dropdown-item value="delete" variant="danger" .disabled=${busy}>
                  <ha-svg-icon slot="icon" .path=${mdiDelete}></ha-svg-icon>Delete
                </ha-dropdown-item>
              </ha-dropdown>
            </ha-list-item-button>
          `;
        })}
      </ha-list-base>
    `;
  }

  private _renderDiffBody(st: DiffState) {
    return html`
      <p class="dialog-text">
        Backup${st.backup.name ? html` “${st.backup.name}”` : nothing}
        ${st.source ? html`of <b>${this._label(st.source)}</b>` : nothing} compared with the current settings of
        <b>${this._device?.name}</b>.
      </p>
      ${st.source ? html`<p class="dialog-text secondary">Per-display settings of the other display are left out.</p>` : nothing}
      ${st.error ? html`<ha-alert alert-type="error">${st.error}</ha-alert>` : nothing}
      ${st.diff === null && !st.error ? html`<div class="loading"><ha-spinner></ha-spinner></div>` : nothing}
      ${st.diff
        ? html`<sep-diff-table
            .diff=${st.diff}
            selectable
            .selected=${st.selected}
            empty-text="The display already has exactly these settings."
            @selection-changed=${(e: CustomEvent<{ selected: Set<string> }>) =>
              (this._diff = { ...st, selected: e.detail.selected })}
          ></sep-diff-table>`
        : nothing}
    `;
  }

  private _renderDiffDialog() {
    const st = this._diff;
    const restoring = !!st?.restoring;
    return html`
      <ha-dialog
        .open=${this._diffOpen}
        width="medium"
        header-title="Restore backup"
        .headerSubtitle=${st ? formatDate(st.backup.created, this._lang) : undefined}
        .preventScrimClose=${restoring}
        @closed=${onDialogClosed(() => {
          this._diffOpen = false;
          this._diff = null;
        })}
      >
        ${st ? this._renderDiffBody(st) : nothing}
        <ha-dialog-footer slot="footer">
          <ha-button slot="secondaryAction" appearance="plain" ?disabled=${restoring} @click=${() => (this._diffOpen = false)}
            >Cancel</ha-button
          >
          <ha-button
            slot="primaryAction"
            variant="danger"
            .loading=${restoring}
            ?disabled=${!st?.diff?.length || !st?.selected.size || restoring}
            @click=${this._restore}
          >
            ${st?.diff && st.selected.size === st.diff.length ? "Restore all" : `Restore ${st?.selected.size ?? 0} selected`}
          </ha-button>
        </ha-dialog-footer>
      </ha-dialog>
    `;
  }

  private _renderCreateDialog() {
    return html`
      <ha-dialog
        .open=${this._createOpen}
        header-title="Create backup"
        .preventScrimClose=${this._creating}
        @closed=${onDialogClosed(() => (this._createOpen = false))}
      >
        <p class="dialog-text">
          Saves the current settings of <b>${this._device?.name}</b>. Named backups are kept when old automatic ones are
          pruned.
        </p>
        <ha-input
          label="Name (optional)"
          autofocus
          .value=${this._newName}
          @input=${(e: Event) => (this._newName = inputValue(e))}
          @keydown=${(e: KeyboardEvent) => e.key === "Enter" && !this._creating && this._create()}
        ></ha-input>
        <ha-dialog-footer slot="footer">
          <ha-button slot="secondaryAction" appearance="plain" ?disabled=${this._creating} @click=${() => (this._createOpen = false)}
            >Cancel</ha-button
          >
          <ha-button slot="primaryAction" .loading=${this._creating} ?disabled=${this._creating} @click=${this._create}
            >Create backup</ha-button
          >
        </ha-dialog-footer>
      </ha-dialog>
    `;
  }

  private _renderOthers(others: string[]) {
    return html`
      <ha-card>
        <div class="card-header">Restore from another display</div>
        <div class="card-content">
          <p>Apply a backup of a different (or removed) display to ${this._device?.name}. Per-display settings are skipped.</p>
          <ha-select
            label="Backups of"
            .options=${others.map((id) => ({ value: id, label: this._label(id) }))}
            .value=${this._source}
            @selected=${(e: SelectedEvent) => {
              e.stopPropagation();
              this._source = e.detail.value;
            }}
          ></ha-select>
        </div>
        ${this._source
          ? html`<div class="card-content list">
              ${this._renderList(this._source, this._all[this._source] ?? [], this._source)}
            </div>`
          : nothing}
      </ha-card>
    `;
  }

  private _renderContent() {
    if (!this.devices.some(isLoaded)) return noDisplaysCard(this, this.devices);
    const others = this._otherIds;
    const device = this._device;
    return html`
      ${device && !device.available
        ? html`<ha-alert alert-type="warning" title="${device.name} is offline">
            Backups can be created and restored once it is back online.
          </ha-alert>`
        : nothing}
      ${this._error
        ? html`<ha-alert alert-type="error" title="Could not load the backups">
            ${this._error}
            <ha-button slot="action" appearance="plain" @click=${this._load}>Retry</ha-button>
          </ha-alert>`
        : nothing}
      <ha-card>
        <div class="card-header">My backups</div>
        <div class="card-content list">
          <p class="intro">
            Backups of the display settings are stored in Home Assistant and are part of Home Assistant backups.
          </p>
          ${this._backups === null
            ? this._loading
              ? html`<div class="loading"><ha-spinner></ha-spinner></div>`
              : nothing
            : this._renderList(this._displayId, this._backups)}
        </div>
      </ha-card>
      ${others.length ? this._renderOthers(others) : nothing}
    `;
  }

  /** Display picker in the app bar; "Reload" of the toolbar menu also reloads the backups. */
  private _menu(): PageMenu {
    if (!this.devices.some(isLoaded)) return {};
    return {
      picker: displayPicker(this.page.hass, this.devices, this.entryId, (entryId) => selectEntry(this, entryId)),
      onReload: () => {
        this._load();
      },
    };
  }

  render() {
    if (!this.page) return nothing;
    const device = this._device;
    const fab =
      device && isLoaded(device)
        ? html`<ha-button slot="fab" size="l" ?disabled=${!device.available} @click=${this._openCreate}>
            <ha-svg-icon slot="start" .path=${mdiPlus}></ha-svg-icon>Create backup
          </ha-button>`
        : nothing;
    return html`
      ${renderPage(this, this.page, html`<div class="content">${this._renderContent()}</div>`, fab, this._menu())}
      ${this._renderDiffDialog()} ${this._renderCreateDialog()}
    `;
  }

  static styles = [
    sharedStyles,
    pageStyles,
    dialogStyles,
    css`
      /* ha-backup-overview-backups */
      .card-content.list {
        padding-left: 0;
        padding-right: 0;
      }
      .card-content.list > p {
        margin-left: var(--ha-space-4);
        margin-right: var(--ha-space-4);
      }
    `,
  ];
}

define("sep-backups-tab", SeBackupsTab);

declare global {
  interface HTMLElementTagNameMap {
    "sep-backups-tab": SeBackupsTab;
  }
}
