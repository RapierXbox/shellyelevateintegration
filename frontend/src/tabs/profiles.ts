import { LitElement, type PropertyValues, css, html, nothing } from "lit";
import {
  mdiCogs,
  mdiDelete,
  mdiDotsVertical,
  mdiDownload,
  mdiPencil,
  mdiPlay,
  mdiPlus,
  mdiStar,
  mdiStarOff,
  mdiStarOutline,
  mdiUpload,
} from "@mdi/js";
import { type DeviceSummary, ElevateApi, type Profile, type Settings, errorMessage, isLoaded, perDeviceKeys } from "../api";
import {
  type DropdownSelectEvent,
  type HaFormSchema,
  type SelectedEvent,
  type ValueChangedEvent,
  isDefined,
  onDialogClosed,
} from "../ha";
import { type PageContext, type PageMenu, pageStyles, renderPage } from "../page";
import { dialogStyles, sharedStyles } from "../styles";
import {
  confirmDialog,
  define,
  downloadJson,
  formatDate,
  isPlainObject,
  pickFile,
  plural,
  refreshDevices,
  slug,
  stopPropagation,
  toast,
  toastError,
} from "../ui";
import type { SeApplyProfileDialog } from "../components/apply-profile-dialog";
import "../components/apply-profile-dialog";

interface EditorState {
  profileId?: string;
  name: string;
  json: string;
  makeDefault: boolean;
  wasDefault: boolean;
}

const PROFILE_FORMAT = "shellyelevateintegration.profile/1";

const EDITOR_SCHEMA: HaFormSchema[] = [
  { name: "name", required: true, selector: { text: {} } },
  { name: "make_default", selector: { boolean: {} } },
];

/** Parse the editor text -> settings or error message. */
const parseSettings = (text: string): { settings?: Settings; error?: string } => {
  if (!text.trim()) return { settings: {} };
  try {
    const value: unknown = JSON.parse(text);
    if (!isPlainObject(value)) return { error: 'The settings must be a JSON object: { "key": value, … }' };
    const redacted = Object.entries(value)
      .filter(([, v]) => v === "**REDACTED**")
      .map(([k]) => k);
    if (redacted.length) return { error: `Redacted values cannot be saved: ${redacted.join(", ")}` };
    return { settings: value };
  } catch (err) {
    return { error: errorMessage(err) };
  }
};

/**
 * `make_default` for profiles/save: a new profile only sends it when ticked (the backend makes
 * the first profile default by itself); an existing one only when it changed.
 */
const makeDefaultParam = (ed: EditorState): boolean | undefined => {
  if (!ed.profileId) return ed.makeDefault || undefined;
  return ed.makeDefault !== ed.wasDefault ? ed.makeDefault : undefined;
};

/** Settings of an imported file: a settings or profile export, or a plain settings object. */
const parseImport = (data: unknown, fileName: string): { settings: Settings; name: string } => {
  if (!isPlainObject(data)) throw new Error("The file does not contain a JSON object");
  const name = fileName.replace(/\.json$/i, "");
  if (isPlainObject(data.settings)) {
    // Settings export ({format, device, settings}) or profile export ({format, name, settings}).
    if (typeof data.name === "string") return { settings: data.settings, name: data.name };
    if (isPlainObject(data.device) && typeof data.device.name === "string") {
      return { settings: data.settings, name: `${data.device.name} profile` };
    }
    return { settings: data.settings, name };
  }
  if (typeof data.format === "string") throw new Error(`Unsupported file format “${data.format}”`);
  return { settings: data, name };
};

/** Profile list with JSON editor, import/export and "apply to displays". */
export class SeProfilesTab extends LitElement {
  static properties = {
    page: { attribute: false },
    api: { attribute: false },
    devices: { attribute: false },
    narrow: { type: Boolean, reflect: true },
    _profiles: { state: true },
    _loading: { state: true },
    _error: { state: true },
    _editor: { state: true },
    _editorOpen: { state: true },
    _saving: { state: true },
    _fromEntry: { state: true },
    _fromBusy: { state: true },
    _busyId: { state: true },
  };

  declare page: PageContext;
  declare api: ElevateApi;
  declare devices: DeviceSummary[];
  declare narrow: boolean;
  declare _profiles: Profile[] | null;
  declare _loading: boolean;
  declare _error: string;
  declare _editor: EditorState | null;
  declare _editorOpen: boolean;
  declare _saving: boolean;
  /** Display the editor's "Load" button takes the settings from. */
  declare _fromEntry: string;
  declare _fromBusy: boolean;
  declare _busyId: string;

  constructor() {
    super();
    this.devices = [];
    this.narrow = false;
    this._profiles = null;
    this._loading = false;
    this._error = "";
    this._editor = null;
    this._editorOpen = false;
    this._saving = false;
    this._fromEntry = "";
    this._fromBusy = false;
    this._busyId = "";
  }

  protected willUpdate(changed: PropertyValues<this>): void {
    if (changed.has("api") && this.api) this._load();
  }

  private get _lang(): string | undefined {
    return this.page?.hass.locale?.language;
  }

  private async _load(): Promise<void> {
    this._loading = true;
    try {
      this._profiles = (await this.api.profilesList()).profiles;
      this._error = "";
    } catch (err) {
      this._error = errorMessage(err);
    } finally {
      this._loading = false;
    }
  }

  // ------------------------------------------------------------------ actions

  private _openEditor(state: EditorState): void {
    this._fromEntry = this.devices.find(isLoaded)?.entry_id ?? "";
    this._editor = state;
    this._editorOpen = true;
  }

  private _new(settings: Settings = {}, name = ""): void {
    this._openEditor({ name, json: JSON.stringify(settings, null, 2), makeDefault: false, wasDefault: false });
  }

  private _edit(p: Profile): void {
    this._openEditor({
      profileId: p.id,
      name: p.name,
      json: JSON.stringify(p.settings, null, 2),
      makeDefault: p.default,
      wasDefault: p.default,
    });
  }

  private _updateEditor(changes: Partial<EditorState>): void {
    if (this._editor) this._editor = { ...this._editor, ...changes };
  }

  private async _fillFromDisplay(): Promise<void> {
    if (!this._editor || !this._fromEntry) return;
    const current = parseSettings(this._editor.json);
    if (current.settings && Object.keys(current.settings).length) {
      const ok = await confirmDialog(this, {
        title: "Replace the settings?",
        text: "The editor content is replaced with the settings of the display.",
        confirmText: "Replace",
      });
      if (!ok) return;
    }
    this._fromBusy = true;
    try {
      const data = await this.api.settingsGet(this._fromEntry);
      const skip = perDeviceKeys(data);
      const settings = Object.fromEntries(
        Object.entries(data.settings)
          .filter(([k]) => !skip.has(k))
          .sort(([a], [b]) => a.localeCompare(b)),
      );
      const name = this.devices.find((d) => d.entry_id === this._fromEntry)?.name;
      this._updateEditor({
        json: JSON.stringify(settings, null, 2),
        name: this._editor?.name || (name ? `${name} profile` : ""),
      });
    } catch (err) {
      toastError(this, "Could not read the display", err);
    } finally {
      this._fromBusy = false;
    }
  }

  private async _saveEditor(): Promise<void> {
    const ed = this._editor;
    if (!ed) return;
    const parsed = parseSettings(ed.json);
    const name = ed.name.trim();
    if (!parsed.settings || !name) return;
    this._saving = true;
    try {
      await this.api.profilesSave({
        profile_id: ed.profileId,
        name,
        settings: parsed.settings,
        make_default: makeDefaultParam(ed),
      });
      toast(this, `Profile “${name}” saved`, "success");
      this._editorOpen = false;
      await this._load();
    } catch (err) {
      toastError(this, "Saving failed", err);
    } finally {
      this._saving = false;
    }
  }

  private async _toggleDefault(p: Profile): Promise<void> {
    this._busyId = p.id;
    try {
      await this.api.profilesSetDefault(p.default ? null : p.id);
      await this._load();
    } catch (err) {
      toastError(this, "", err);
    } finally {
      this._busyId = "";
    }
  }

  private async _delete(p: Profile): Promise<void> {
    const ok = await confirmDialog(this, {
      title: `Delete “${p.name}”?`,
      text: `The profile is deleted. Displays keep their current settings.${p.default ? "\n\nThis is the default profile – no profile will be the default afterwards." : ""}`,
      confirmText: "Delete",
      destructive: true,
    });
    if (!ok) return;
    this._busyId = p.id;
    try {
      await this.api.profilesDelete(p.id);
      toast(this, `Profile “${p.name}” deleted`, "success");
      await this._load();
    } catch (err) {
      toastError(this, "Delete failed", err);
    } finally {
      this._busyId = "";
    }
  }

  private _export(p: Profile): void {
    downloadJson(`profile-${slug(p.name)}.json`, {
      format: PROFILE_FORMAT,
      exported: new Date().toISOString(),
      name: p.name,
      settings: p.settings,
    });
  }

  private async _import(): Promise<void> {
    const file = await pickFile(".json,application/json");
    if (!file) return;
    try {
      const { settings, name } = parseImport(JSON.parse(await file.text()), file.name);
      this._new(settings, name);
      toast(this, `Imported ${plural(Object.keys(settings).length, "setting")} from ${file.name} – review and save`, "info");
    } catch (err) {
      toastError(this, "Import failed", err);
    }
  }

  private async _apply(p: Profile): Promise<void> {
    await this.updateComplete;
    this.renderRoot.querySelector<SeApplyProfileDialog>("sep-apply-profile-dialog")?.show(p.id, []);
  }

  private _onMenu(p: Profile, ev: DropdownSelectEvent): void {
    switch (ev.detail.item.value) {
      case "apply":
        this._apply(p);
        break;
      case "default":
        this._toggleDefault(p);
        break;
      case "edit":
        this._edit(p);
        break;
      case "download":
        this._export(p);
        break;
      case "delete":
        this._delete(p);
        break;
      default:
        break;
    }
  }

  // ------------------------------------------------------------------ rendering

  private _renderFromDisplay() {
    const loaded = this.devices.filter(isLoaded);
    if (!loaded.length) return nothing;
    return html`<div class="from">
      <ha-select
        label="Take settings from a display"
        .options=${loaded.map((d) => ({ value: d.entry_id, label: d.name }))}
        .value=${this._fromEntry}
        @selected=${(e: SelectedEvent) => {
          e.stopPropagation();
          this._fromEntry = e.detail.value;
        }}
      ></ha-select>
      <ha-button appearance="plain" .loading=${this._fromBusy} ?disabled=${this._fromBusy} @click=${this._fillFromDisplay}
        >Load</ha-button
      >
    </div>`;
  }

  private _renderJsonEditor(ed: EditorState, parsed: ReturnType<typeof parseSettings>) {
    const count = parsed.settings ? Object.keys(parsed.settings).length : 0;
    return html`<div>
      <div class="editor-label">Settings (JSON)</div>
      ${isDefined("ha-code-editor")
        ? html`<ha-code-editor
            mode="yaml"
            .hass=${this.page.hass}
            .value=${ed.json}
            .error=${!!parsed.error}
            disable-fullscreen
            in-dialog
            @value-changed=${(e: ValueChangedEvent<string>) => {
              e.stopPropagation();
              this._updateEditor({ json: e.detail.value });
            }}
          ></ha-code-editor>`
        : html`<textarea
            class="fallback"
            spellcheck="false"
            .value=${ed.json}
            @input=${(e: Event) => this._updateEditor({ json: (e.currentTarget as HTMLTextAreaElement).value })}
          ></textarea>`}
      <div class="hint ${parsed.error ? "error" : "secondary"}">
        ${parsed.error ? parsed.error : html`Valid JSON · ${plural(count, "setting")}. Per-display settings are removed when saving.`}
      </div>
    </div>`;
  }

  private _renderEditor() {
    const ed = this._editor;
    const parsed = ed ? parseSettings(ed.json) : {};
    return html`
      <ha-dialog
        .open=${this._editorOpen}
        width="large"
        .headerTitle=${ed?.profileId ? "Edit profile" : "New profile"}
        .preventScrimClose=${this._saving}
        @closed=${onDialogClosed(() => {
          this._editorOpen = false;
          this._editor = null;
        })}
      >
        ${ed
          ? html`
              <div class="stack">
                <ha-form
                  .hass=${this.page.hass}
                  .data=${{ name: ed.name, make_default: ed.makeDefault }}
                  .schema=${EDITOR_SCHEMA}
                  .computeLabel=${(s: HaFormSchema) => (s.name === "name" ? "Name" : "Default profile for new displays")}
                  .computeHelper=${(s: HaFormSchema) =>
                    s.name === "make_default" ? "Pre-selected when a new display is installed." : undefined}
                  @value-changed=${(e: ValueChangedEvent<{ name?: string; make_default?: boolean }>) => {
                    e.stopPropagation();
                    this._updateEditor({ name: e.detail.value.name ?? "", makeDefault: !!e.detail.value.make_default });
                  }}
                ></ha-form>
                ${this._renderFromDisplay()} ${this._renderJsonEditor(ed, parsed)}
              </div>
            `
          : nothing}
        <ha-dialog-footer slot="footer">
          <ha-button slot="secondaryAction" appearance="plain" ?disabled=${this._saving} @click=${() => (this._editorOpen = false)}
            >Cancel</ha-button
          >
          <ha-button
            slot="primaryAction"
            .loading=${this._saving}
            ?disabled=${this._saving || !!parsed.error || !ed?.name.trim()}
            @click=${this._saveEditor}
          >
            Save
          </ha-button>
        </ha-dialog-footer>
      </ha-dialog>
    `;
  }

  private _renderProfile(p: Profile) {
    const busy = this._busyId === p.id;
    return html`
      <ha-list-item-button @click=${() => this._edit(p)}>
        <ha-svg-icon slot="start" .path=${mdiCogs}></ha-svg-icon>
        <span slot="headline">
          ${p.name} ${p.default ? html`<ha-svg-icon .path=${mdiStar} title="Default profile" role="img" aria-label="Default profile"></ha-svg-icon>` : nothing}
        </span>
        <span slot="supporting-text">
          ${plural(Object.keys(p.settings ?? {}).length, "setting")} · Updated ${formatDate(p.updated ?? p.created, this._lang)}
        </span>
        ${busy ? html`<ha-spinner slot="end" size="small"></ha-spinner>` : nothing}
        <ha-dropdown
          slot="end"
          placement="bottom-end"
          @click=${stopPropagation}
          @wa-select=${(e: DropdownSelectEvent) => this._onMenu(p, e)}
        >
          <ha-icon-button slot="trigger" .label=${"Menu"} .path=${mdiDotsVertical}></ha-icon-button>
          <ha-dropdown-item value="apply">
            <ha-svg-icon slot="icon" .path=${mdiPlay}></ha-svg-icon>Apply to displays
          </ha-dropdown-item>
          <ha-dropdown-item value="default" .disabled=${busy}>
            <ha-svg-icon slot="icon" .path=${p.default ? mdiStarOff : mdiStarOutline}></ha-svg-icon>
            ${p.default ? "Unset as default" : "Set as default"}
          </ha-dropdown-item>
          <ha-dropdown-item value="edit">
            <ha-svg-icon slot="icon" .path=${mdiPencil}></ha-svg-icon>Edit
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
  }

  private _renderList() {
    if (this._profiles === null) {
      return this._loading ? html`<div class="loading"><ha-spinner></ha-spinner></div>` : nothing;
    }
    if (!this._profiles.length) return nothing;
    return html`<ha-list-base aria-label="Profiles">${this._profiles.map((p) => this._renderProfile(p))}</ha-list-base>`;
  }

  /** "Import profile" in the toolbar menu, like "Upload backup" on Settings → System → Backups. */
  private _menu(): PageMenu {
    return {
      items: html`<ha-dropdown-item value="import">
        <ha-svg-icon slot="icon" .path=${mdiUpload}></ha-svg-icon>Import profile
      </ha-dropdown-item>`,
      onSelect: (value) => {
        if (value === "import") this._import();
      },
    };
  }

  private _renderContent() {
    const empty = this._profiles !== null && !this._profiles.length;
    return html`
      <div class="content">
        ${this._error ? html`<ha-alert alert-type="error">${this._error}</ha-alert>` : nothing}
        <ha-card>
          <div class="card-header">Profiles</div>
          <div class="card-content list">
            <p>
              Profiles are named sets of settings you can apply to several displays. The default profile is used when a
              new display is installed. Per-display settings (IDs, names) are never part of a profile.
            </p>
            ${empty
              ? html`<p>No profiles yet. Create one, import a settings export or use “Save as profile” in the Settings tab.</p>`
              : nothing}
            ${this._renderList()}
          </div>
        </ha-card>
      </div>
    `;
  }

  render() {
    if (!this.page) return nothing;
    const fab = html`<ha-button slot="fab" size="l" @click=${() => this._new()}>
      <ha-svg-icon slot="start" .path=${mdiPlus}></ha-svg-icon>New profile
    </ha-button>`;
    return html`
      ${renderPage(this, this.page, this._renderContent(), fab, this._menu())} ${this._renderEditor()}
      <sep-apply-profile-dialog
        .api=${this.api}
        .devices=${this.devices}
        .profiles=${this._profiles ?? []}
        @applied=${() => refreshDevices(this)}
      ></sep-apply-profile-dialog>
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
      /* assist-pref */
      ha-list-item-button span ha-svg-icon {
        color: currentColor;
        --mdc-icon-size: 16px;
        vertical-align: text-bottom;
      }
      .from {
        display: flex;
        align-items: center;
        gap: var(--ha-space-2);
      }
      .from ha-select {
        flex: 1;
        min-width: 0;
      }
      .editor-label {
        margin-bottom: var(--ha-space-2);
      }
      ha-code-editor {
        display: block;
        min-height: 240px;
        --code-mirror-max-height: 50vh;
      }
      .hint {
        margin-top: var(--ha-space-2);
        font-size: var(--ha-font-size-s);
      }
    `,
  ];
}

define("sep-profiles-tab", SeProfilesTab);

declare global {
  interface HTMLElementTagNameMap {
    "sep-profiles-tab": SeProfilesTab;
  }
}
