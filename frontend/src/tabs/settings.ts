import { LitElement, type PropertyValues, type TemplateResult, css, html, nothing } from "lit";
import { mdiCogs, mdiContentCopy, mdiContentSave, mdiDownload } from "@mdi/js";
import {
  type DeviceSummary,
  ElevateApi,
  type SettingDef,
  type Settings,
  type SettingsGetResult,
  deviceName,
  errorMessage,
  isLoaded,
  perDeviceKeys,
} from "../api";
import {
  type HaFormSchema,
  type SelectedEvent,
  type UnsubscribeFunc,
  type ValueChangedEvent,
  fireEvent,
  inputValue,
  isChecked,
  isDefined,
  onDialogClosed,
} from "../ha";
import { type PageContext, type PageMenu, displayPicker, noDisplaysCard, pageStyles, renderPage } from "../page";
import { dialogStyles, sharedStyles } from "../styles";
import { confirmDialog, define, downloadJson, formatValue, plural, selectEntry, slug, toast, toastError } from "../ui";
import type { KeyOption } from "../components/key-picker";
import "../components/key-picker";
import { type Visibility, VisibilityEvaluator, visibilityHint } from "../visibility";

const CATEGORY_LABELS: Record<string, string> = {
  general: "General",
  display: "Display",
  screensaver: "Screensaver",
  inputs: "Inputs & buttons",
  mqtt: "MQTT",
  voice: "Voice assistant",
  bluetooth: "Bluetooth",
  media: "Media",
  advanced: "Advanced",
};
const CATEGORY_ORDER = Object.keys(CATEGORY_LABELS);
/** Categories shown as collapsed cards after the others. */
const COLLAPSED: Record<string, { header: string; secondary: string }> = {
  deprecated: { header: "Deprecated", secondary: "Settings of features the app will remove" },
  other: { header: "Not described by the display", secondary: "Raw values the settings schema does not know" },
};
const COLLAPSED_ORDER = Object.keys(COLLAPSED);

const same = (a: unknown, b: unknown): boolean => JSON.stringify(a) === JSON.stringify(b);

const categoryLabel = (c: string): string => CATEGORY_LABELS[c] ?? c.charAt(0).toUpperCase() + c.slice(1);

/** Text shown in a text/number input for a value. */
const toText = (def: SettingDef, value: unknown): string => {
  if (value === null || value === undefined) return "";
  if (def.type === "string_list") return Array.isArray(value) ? value.join(", ") : String(value);
  return String(value);
};

/** Parse input text -> [ok, value]. */
const parseText = (def: SettingDef, text: string): [boolean, unknown] => {
  switch (def.type) {
    case "int":
    case "float": {
      if (text.trim() === "") return [false, null];
      const n = Number(text);
      if (!Number.isFinite(n)) return [false, null];
      if (def.type === "int" && !Number.isInteger(n)) return [false, null];
      if (def.min !== null && def.min !== undefined && n < def.min) return [false, n];
      if (def.max !== null && def.max !== undefined && n > def.max) return [false, n];
      return [true, n];
    }
    case "string_list":
      return [
        true,
        text
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean),
      ];
    default:
      return [true, text];
  }
};

const KEYS_MODE_OPTIONS = [
  { value: "all", label: "All portable settings" },
  { value: "selected", label: "Only selected settings" },
];

type KeysMode = "all" | "selected";
type Dialog = "" | "export" | "copy" | "profile";

interface DialogContent {
  title: string;
  body: TemplateResult;
  primary: TemplateResult;
}

/** Settings editor of one display, with export / copy to other displays / save as profile. */
export class SeSettingsTab extends LitElement {
  static properties = {
    page: { attribute: false },
    api: { attribute: false },
    devices: { attribute: false },
    entryId: {},
    narrow: { type: Boolean, reflect: true },
    _data: { state: true },
    _loading: { state: true },
    _error: { state: true },
    _edits: { state: true },
    _text: { state: true },
    _invalid: { state: true },
    _filter: { state: true },
    _saving: { state: true },
    _dialog: { state: true },
    _includeSecrets: { state: true },
    _targets: { state: true },
    _keysMode: { state: true },
    _keys: { state: true },
    _profileName: { state: true },
    _profileDefault: { state: true },
    _dialogBusy: { state: true },
  };

  declare page: PageContext;
  declare api: ElevateApi;
  declare devices: DeviceSummary[];
  declare entryId: string;
  declare narrow: boolean;
  declare _data: SettingsGetResult | null;
  declare _loading: boolean;
  declare _error: string;
  /** Changed values (key -> new value). */
  declare _edits: Settings;
  /** Raw input text of number / list fields (may be invalid). */
  declare _text: Record<string, string>;
  declare _invalid: Set<string>;
  declare _filter: string;
  declare _saving: boolean;
  declare _dialog: Dialog;
  declare _includeSecrets: boolean;
  declare _targets: string[];
  declare _keysMode: KeysMode;
  declare _keys: Set<string>;
  declare _profileName: string;
  declare _profileDefault: boolean;
  declare _dialogBusy: boolean;

  /** entry id the current data belongs to */
  private _loadedFor = "";
  /** Last state sent with `se-unsaved`. */
  private _reportedUnsaved = "";
  /** Dialog whose content stays rendered until its closing animation is done. */
  private _openDialogName: Dialog = "";
  /** Live setting changes of the display in `_subscribedFor`. */
  private _settingsSub?: Promise<UnsubscribeFunc | undefined>;
  private _subscribedFor = "";

  constructor() {
    super();
    this.devices = [];
    this.entryId = "";
    this.narrow = false;
    this._data = null;
    this._loading = false;
    this._error = "";
    this._edits = {};
    this._text = {};
    this._invalid = new Set();
    this._filter = "";
    this._saving = false;
    this._dialog = "";
    this._includeSecrets = false;
    this._targets = [];
    this._keysMode = "all";
    this._keys = new Set();
    this._profileName = "";
    this._profileDefault = false;
    this._dialogBusy = false;
  }

  connectedCallback(): void {
    super.connectedCallback();
    if (this._loadedFor) this._subscribe(this._loadedFor);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._unsubscribe();
  }

  protected willUpdate(changed: PropertyValues<this>): void {
    if ((changed.has("entryId") || changed.has("api")) && this.api && this.entryId && this.entryId !== this._loadedFor) {
      this._load();
    }
  }

  protected updated(): void {
    // Tell the panel about unsaved changes (it asks before they are dropped by leaving the tab).
    const count = this._dirty ? Math.max(this._editCount, 1) : 0;
    const key = count ? `${count}:${this.entryId}` : "";
    if (key !== this._reportedUnsaved) {
      this._reportedUnsaved = key;
      fireEvent(this, "se-unsaved", count ? { count, name: this._device?.name ?? "the display" } : null);
    }
  }

  private get _device(): DeviceSummary | undefined {
    return this.devices.find((d) => d.entry_id === this.entryId);
  }

  private get _editCount(): number {
    return Object.keys(this._edits).length;
  }

  private get _dirty(): boolean {
    return this._editCount > 0 || this._blockingInvalid.length > 0;
  }

  /** Visibility of the settings with the unsaved edits applied (build again after edits). */
  private _evaluator(): VisibilityEvaluator | null {
    return this._data ? new VisibilityEvaluator(this._data, (key) => this._value(key)) : null;
  }

  /** Invalid inputs of shown settings; one of a setting that is not shown cannot block saving. */
  private get _blockingInvalid(): string[] {
    const ev = this._evaluator();
    return [...this._invalid].filter((key) => !ev || ev.visible(key));
  }

  private _resetEdits(): void {
    this._edits = {};
    this._text = {};
    this._invalid = new Set();
  }

  private async _load(): Promise<void> {
    const entryId = this.entryId;
    // Another display: drop the old one's settings right away, so nothing is edited (and saved
    // to the new display) against the values of the previous one.
    if (this._data && this._loadedFor !== entryId) {
      this._data = null;
      this._resetEdits();
    }
    this._loadedFor = entryId;
    // before reading so no change between the read and the subscription is lost
    if (this._subscribedFor !== entryId) this._subscribe(entryId);
    this._loading = true;
    this._error = "";
    try {
      const data = await this.api.settingsGet(entryId);
      if (entryId !== this.entryId) return;
      this._data = data;
      this._resetEdits();
    } catch (err) {
      if (entryId !== this.entryId) return;
      this._data = null;
      this._error = errorMessage(err);
    } finally {
      if (entryId === this.entryId) this._loading = false;
    }
  }

  private _subscribe(entryId: string): void {
    this._unsubscribe();
    this._subscribedFor = entryId;
    this._settingsSub = this.api
      .subscribeSettings(entryId, (changes) => this._applyRemote(entryId, changes))
      .catch(() => undefined);
  }

  private _unsubscribe(): void {
    const sub = this._settingsSub;
    this._settingsSub = undefined;
    this._subscribedFor = "";
    sub?.then((unsub) => unsub?.()).catch(() => undefined);
  }

  /**
   * Settings changed by Home Assistant or on the display: show them (and the settings they show or
   * hide) right away. Unsaved edits stay unless they now match the display.
   */
  private _applyRemote(entryId: string, changes: Settings): void {
    if (!this._data || entryId !== this._loadedFor || entryId !== this.entryId) return;
    const edits = { ...this._edits };
    const text = { ...this._text };
    for (const [key, value] of Object.entries(changes)) {
      if (key in edits && !same(edits[key], value)) continue;
      delete edits[key];
      // input text of a field that is not being edited shows the new value
      if (!this._invalid.has(key)) delete text[key];
    }
    this._data = { ...this._data, settings: { ...this._data.settings, ...changes } };
    this._edits = edits;
    this._text = text;
  }

  /** Read the settings again (asks first when there are unsaved changes). */
  private async _reload(): Promise<boolean> {
    if (this._dirty && !(await this._confirmDiscard())) return false;
    this._load();
    return true;
  }

  private _confirmDiscard(): Promise<boolean> {
    return confirmDialog(this, {
      title: "Discard unsaved changes?",
      text: `${plural(this._editCount, "setting")} changed on ${this._device?.name ?? "this display"} will be lost.`,
      confirmText: "Discard",
      destructive: true,
    });
  }

  private async _selectDevice(entryId: string): Promise<void> {
    if (!entryId || entryId === this.entryId) return;
    if (this._dirty && !(await this._confirmDiscard())) return;
    this._resetEdits();
    selectEntry(this, entryId);
  }

  // ------------------------------------------------------------------ editing

  private _original(key: string): unknown {
    return this._data?.settings[key];
  }

  private _value(key: string): unknown {
    return key in this._edits ? this._edits[key] : this._original(key);
  }

  private _setValue(key: string, value: unknown): void {
    const edits = { ...this._edits };
    if (same(value, this._original(key))) delete edits[key];
    else edits[key] = value;
    this._edits = edits;
  }

  private _setText(def: SettingDef, text: string): void {
    this._text = { ...this._text, [def.key]: text };
    const [ok, value] = parseText(def, text);
    const invalid = new Set(this._invalid);
    if (ok) {
      invalid.delete(def.key);
      this._setValue(def.key, value);
    } else {
      invalid.add(def.key);
    }
    this._invalid = invalid;
  }

  private async _save(): Promise<void> {
    if (!this._data || this._loading || this._loadedFor !== this.entryId || this._blockingInvalid.length) return;
    const changes = { ...this._edits };
    // the last valid value of an input that is invalid now and no longer shown is not what the user typed
    for (const key of this._invalid) delete changes[key];
    const keys = Object.keys(changes);
    if (!keys.length) return;
    this._saving = true;
    try {
      const result = await this.api.settingsSet(this.entryId, changes);
      const ignored = result.ignored ?? [];
      const saved = keys.filter((key) => !ignored.includes(key));
      const label = (key: string): string => this._data?.schema.find((d) => d.key === key)?.label || key;
      const restart = this._data.schema.filter((d) => d.requires_restart && saved.includes(d.key));
      const details = [
        ...(ignored.length ? [`Not applied (the display does not know them): ${ignored.map(label).join(", ")}`] : []),
        ...(restart.length ? [`Takes effect after an app restart: ${restart.map((d) => d.label || d.key).join(", ")}`] : []),
      ];
      const name = this._device?.name ?? "the display";
      toast(
        this,
        ignored.length
          ? `Saved ${plural(saved.length, "setting")} on ${name}, not applied: ${ignored.map(label).join(", ")}`
          : `Saved ${plural(saved.length, "setting")} on ${name}`,
        ignored.length ? "warning" : "success",
        details.length ? details : undefined,
      );
      await this._load();
    } catch (err) {
      toastError(this, "Saving failed", err);
    } finally {
      this._saving = false;
    }
  }

  // ------------------------------------------------------------------ dialogs

  private _portableKeyOptions(): KeyOption[] {
    if (!this._data) return [];
    const perDevice = perDeviceKeys(this._data);
    // not gated on visibility: a profile may carry settings for features that are off here
    return this._data.schema
      .filter((d) => !perDevice.has(d.key) && !d.hidden && !d.read_only)
      .map((d) => ({ key: d.key, label: d.label ?? d.key }));
  }

  private _openDialog(dialog: Exclude<Dialog, "">): void {
    this._dialogBusy = false;
    this._keysMode = "all";
    this._keys = new Set();
    if (dialog === "copy") this._targets = [];
    if (dialog === "profile") {
      this._profileName = this._device?.name ? `${this._device.name} profile` : "";
      this._profileDefault = false;
    }
    this._dialog = dialog;
    this._openDialogName = dialog;
  }

  private _closeDialog(): void {
    if (this._dialogBusy) return;
    this._dialog = "";
  }

  private _dialogClosed = onDialogClosed(() => {
    this._dialog = "";
    this._openDialogName = "";
    this.requestUpdate();
  });

  /** Run a dialog action; the dialog closes when it succeeds. */
  private async _runDialogAction(failure: string, action: () => Promise<void>): Promise<void> {
    this._dialogBusy = true;
    try {
      await action();
      this._dialog = "";
    } catch (err) {
      toastError(this, failure, err);
    } finally {
      this._dialogBusy = false;
    }
  }

  private _export(): Promise<void> {
    return this._runDialogAction("Export failed", async () => {
      const data = await this.api.settingsExport(this.entryId, this._includeSecrets);
      const date = new Date().toISOString().slice(0, 10);
      downloadJson(`${slug(this._device?.name ?? "display")}-settings-${date}.json`, data);
    });
  }

  private async _copy(): Promise<void> {
    const targets = [...this._targets];
    const keys = this._keysMode === "selected" ? [...this._keys] : undefined;
    const ok = await confirmDialog(this, {
      title: `Copy settings to ${plural(targets.length, "display")}?`,
      text: `${keys ? plural(keys.length, "setting") : "All portable settings"} of ${this._device?.name} are written to the displays below. Per-display settings are never copied. A backup of each target is taken first.`,
      items: targets.map((id) => deviceName(this.devices, id)),
      confirmText: "Copy",
    });
    if (!ok) return;
    await this._runDialogAction("Copy failed", async () => {
      const { results, errors } = await this.api.settingsCopy(this.entryId, targets, keys);
      const nameOf = (deviceId: string) =>
        this.devices.find((d) => d.device_id === deviceId || d.entry_id === deviceId)?.name ?? deviceId;
      const failed = Object.entries(errors).map(([deviceId, error]) => `${nameOf(deviceId)}: ${error}`);
      const copied = Object.entries(results);
      if (!copied.length && failed.length) throw new Error(failed.join("; "));
      const details = copied.map(
        ([deviceId, changes]) =>
          `${nameOf(deviceId)}: ${changes.length ? plural(changes.length, "setting") + " changed" : "already up to date"}`,
      );
      if (failed.length) {
        toast(this, `Settings copied to ${copied.length} of ${plural(targets.length, "display")}`, "warning", [
          ...failed,
          ...details,
        ]);
      } else {
        toast(this, `Settings copied to ${plural(targets.length, "display")}`, "success", details);
      }
    });
  }

  private async _saveProfile(): Promise<void> {
    const name = this._profileName.trim();
    if (!name) return;
    await this._runDialogAction("Saving the profile failed", async () => {
      await this.api.profilesSave({
        name,
        from_entry_id: this.entryId,
        // Unsaved edits are overlaid on the display's current settings by the backend.
        settings: this._editCount ? { ...this._edits } : undefined,
        keys: this._keysMode === "selected" ? [...this._keys] : undefined,
        make_default: this._profileDefault || undefined,
      });
      toast(this, `Profile “${name}” saved`, "success");
    });
  }

  // ------------------------------------------------------------------ rendering: editor

  private _renderControl(def: SettingDef, locked: boolean) {
    const value = this._value(def.key);
    const invalid = this._invalid.has(def.key);
    const secret = def.secret || this._data?.secret.includes(def.key);
    const label = def.label ?? def.key;
    // read-only while the settings are (re)loaded: edits would be dropped by the load
    const disabled = this._loading || locked;
    switch (def.type) {
      case "bool":
        return html`<ha-switch
          .checked=${value === true}
          .disabled=${disabled}
          aria-label=${label}
          @change=${(e: Event) => this._setValue(def.key, isChecked(e))}
        ></ha-switch>`;
      case "enum": {
        const options = def.options ?? [];
        const idx = options.findIndex((o) => same(o.value, value) || String(o.value) === String(value));
        const items = options.map((o, i) => ({ value: String(i), label: o.label }));
        if (idx < 0) items.unshift({ value: "-1", label: formatValue(value) });
        return html`<ha-select
          class="ctrl"
          .label=${undefined}
          aria-label=${label}
          .options=${items}
          .value=${String(idx)}
          .disabled=${disabled}
          @selected=${(e: SelectedEvent) => {
            e.stopPropagation();
            const i = Number(e.detail.value);
            if (i >= 0 && options[i]) this._setValue(def.key, options[i].value);
          }}
        ></ha-select>`;
      }
      case "int":
      case "float":
        return html`<ha-input
          class="ctrl"
          .disabled=${disabled}
          type="number"
          aria-label=${label}
          .invalid=${invalid}
          .min=${def.min ?? undefined}
          .max=${def.max ?? undefined}
          .step=${def.step ?? (def.type === "int" ? 1 : "any")}
          .value=${this._text[def.key] ?? toText(def, value)}
          @input=${(e: Event) => this._setText(def, inputValue(e))}
        >
          ${def.unit ? html`<span slot="end" class="unit">${def.unit}</span>` : nothing}
        </ha-input>`;
      case "string_list":
        return html`<ha-input
          class="ctrl"
          .disabled=${disabled}
          aria-label=${label}
          placeholder="value1, value2"
          .value=${this._text[def.key] ?? toText(def, value)}
          @input=${(e: Event) => this._setText(def, inputValue(e))}
        ></ha-input>`;
      default:
        return html`<ha-input
          class="ctrl"
          .disabled=${disabled}
          aria-label=${label}
          .type=${secret ? "password" : "text"}
          ?password-toggle=${secret}
          autocomplete=${secret ? "new-password" : "off"}
          .value=${value === null || value === undefined ? "" : String(value)}
          @input=${(e: Event) => this._setValue(def.key, inputValue(e))}
        ></ha-input>`;
    }
  }

  /** One setting as a list row (headline, supporting text, control at the end) like Backup → Settings. */
  private _renderField(def: SettingDef, vis: Visibility, ev: VisibilityEvaluator) {
    const invalid = this._invalid.has(def.key);
    const perDevice = def.per_device || this._data?.per_device.includes(def.key);
    const managed = this._data?.managed?.[def.key];
    const range =
      (def.type === "int" || def.type === "float") && (def.min != null || def.max != null)
        ? `${def.min ?? "…"} – ${def.max ?? "…"}${def.unit ? ` ${def.unit}` : ""}`
        : "";
    const replacement = def.replaced_by ? (ev.def(def.replaced_by)?.label ?? def.replaced_by) : "";
    const notes = [
      def.key,
      range,
      perDevice ? "Per display" : "",
      def.requires_restart ? "Requires an app restart" : "",
      replacement ? `Replaced by ${replacement}` : "",
    ].filter(Boolean);
    // only search results are rendered while not visible: they show why instead of a usable control
    const lockReason = !vis.visible
      ? visibilityHint(vis)
      : (managed ?? (def.read_only ? "Read-only" : ""));
    return html`
      <ha-list-item-base class=${vis.visible ? "" : "unavailable"}>
        <span slot="headline">${def.label || def.key}</span>
        <span slot="supporting-text"
          >${def.description ? html`${def.description}<br />` : nothing}${notes.join(" · ")}${lockReason
            ? html`<br /><span class="lock">${lockReason}</span>`
            : nothing}${invalid
            ? html`<br /><span class="error">Invalid value${range ? ` (${range})` : ""}</span>`
            : nothing}</span
        >
        <div slot="end" class="end">${this._renderControl(def, !!lockReason)}</div>
      </ha-list-item-base>
    `;
  }

  private _renderRows(defs: SettingDef[], ev: VisibilityEvaluator) {
    return html`<ha-list-base class="rows">${defs.map((d) => this._renderField(d, ev.get(d.key), ev))}</ha-list-base>`;
  }

  /**
   * One card per category, like the cards of Settings → System → Backups → Settings. Settings that
   * cannot be configured right now are left out; a search also finds them, shown disabled with why.
   */
  private _renderCategories(data: SettingsGetResult) {
    const ev = this._evaluator();
    if (!ev) return nothing;
    const f = this._filter.trim().toLowerCase();
    const groups = new Map<string, SettingDef[]>();
    for (const def of data.schema) {
      if (def.hidden) continue;
      if (f && !def.key.toLowerCase().includes(f) && !(def.label ?? "").toLowerCase().includes(f)) continue;
      if (!f && !ev.visible(def.key)) continue;
      const cat = def.deprecated ? "deprecated" : def.category || "general";
      groups.set(cat, [...(groups.get(cat) ?? []), def]);
    }
    const rank = (c: string) => (CATEGORY_ORDER.includes(c) ? CATEGORY_ORDER.indexOf(c) : 99);
    const cats = [...groups.keys()]
      .filter((c) => !(c in COLLAPSED))
      .sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
    const collapsed = COLLAPSED_ORDER.filter((c) => groups.has(c));
    if (!cats.length && !collapsed.length) {
      return f
        ? html`<ha-card><div class="card-content">No settings match “${this._filter}”.</div></ha-card>`
        : nothing;
    }
    return html`
      ${cats.map(
        (cat) => html`
          <ha-card>
            <h1 class="card-header">${categoryLabel(cat)}</h1>
            <div class="card-content list">${this._renderRows(groups.get(cat) ?? [], ev)}</div>
          </ha-card>
        `,
      )}
      ${collapsed.map(
        (cat) => html`
          <ha-card>
            <ha-expansion-panel
              class="collapsed"
              .header=${COLLAPSED[cat].header}
              .secondary=${COLLAPSED[cat].secondary}
              .expanded=${!!f}
            >
              ${this._renderRows(groups.get(cat) ?? [], ev)}
            </ha-expansion-panel>
          </ha-card>
        `,
      )}
    `;
  }

  /** Reload / export / copy / save as profile in the toolbar menu (like "Upload backup" on Backups). */
  private _menu(): PageMenu {
    const loadedCount = this.devices.filter(isLoaded).length;
    const off = !this._data;
    if (!loadedCount) return {};
    return {
      items: html`
        <ha-dropdown-item value="export" .disabled=${off}>
          <ha-svg-icon slot="icon" .path=${mdiDownload}></ha-svg-icon>Export settings
        </ha-dropdown-item>
        <ha-dropdown-item value="copy" .disabled=${off || loadedCount < 2}>
          <ha-svg-icon slot="icon" .path=${mdiContentCopy}></ha-svg-icon>Copy to other displays
        </ha-dropdown-item>
        <ha-dropdown-item value="profile" .disabled=${off}>
          <ha-svg-icon slot="icon" .path=${mdiCogs}></ha-svg-icon>Save as profile
        </ha-dropdown-item>
      `,
      onSelect: (value) => {
        if (value === "export" || value === "copy" || value === "profile") this._openDialog(value);
      },
      onReload: () => this._reload(),
    };
  }

  private _renderEditor() {
    if (!this._data) {
      return this._loading ? html`<div class="loading"><ha-spinner></ha-spinner></div>` : nothing;
    }
    const device = this._device;
    return html`
      ${device && !device.available
        ? html`<ha-alert alert-type="warning" title="${device.name} is offline">
            Changes can only be saved while it is online.
          </ha-alert>`
        : nothing}
      ${this._device?.legacy
        ? html`<ha-alert alert-type="info">
            This display runs the legacy app – settings use a built-in description and some may not apply.
          </ha-alert>`
        : nothing}
      ${this._renderCategories(this._data)}
    `;
  }

  /** Search bar below the app bar, as on Settings → System → Logs, with the display picker at its end. */
  private _renderSearch() {
    const onFilter = (e: Event) => (this._filter = inputValue(e));
    const count = this._data?.schema.filter((d) => !d.hidden).length ?? 0;
    const placeholder = this._data ? `Search ${plural(count, "setting")}` : "Search settings";
    return html`<div class="search">
      ${isDefined("ha-input-search")
        ? html`<ha-input-search
            appearance="outlined"
            .placeholder=${placeholder}
            .value=${this._filter}
            .disabled=${!this._data}
            @input=${onFilter}
          ></ha-input-search>`
        : html`<ha-input .placeholder=${placeholder} .value=${this._filter} .disabled=${!this._data} @input=${onFilter}></ha-input>`}
      ${displayPicker(this.page.hass, this.devices, this.entryId, (entryId) => this._selectDevice(entryId))}
    </div>`;
  }

  // ------------------------------------------------------------------ rendering: dialogs

  private _renderKeysChoice() {
    const schema: HaFormSchema[] = [
      { name: "keys_mode", required: true, selector: { select: { mode: "list", options: KEYS_MODE_OPTIONS } } },
    ];
    return html`
      <ha-form
        .hass=${this.page.hass}
        .data=${{ keys_mode: this._keysMode }}
        .schema=${schema}
        .computeLabel=${() => "Settings to include"}
        @value-changed=${(e: ValueChangedEvent<{ keys_mode?: KeysMode }>) => {
          e.stopPropagation();
          this._keysMode = e.detail.value.keys_mode === "selected" ? "selected" : "all";
        }}
      ></ha-form>
      ${this._keysMode === "selected"
        ? html`<sep-key-picker
            .options=${this._portableKeyOptions()}
            .selected=${this._keys}
            @selection-changed=${(e: CustomEvent<{ selected: Set<string> }>) => (this._keys = e.detail.selected)}
          ></sep-key-picker>`
        : nothing}
    `;
  }

  private _exportDialog(busy: boolean): DialogContent {
    const schema: HaFormSchema[] = [{ name: "include_secrets", selector: { boolean: {} } }];
    return {
      title: "Export settings",
      body: html`
        <p class="dialog-text">
          Downloads the settings of <b>${this._device?.name}</b> as a JSON file. It can be imported as a profile.
        </p>
        <ha-form
          .hass=${this.page.hass}
          .data=${{ include_secrets: this._includeSecrets }}
          .schema=${schema}
          .computeLabel=${() => "Include secrets"}
          .computeHelper=${() => "Passwords and tokens"}
          @value-changed=${(e: ValueChangedEvent<{ include_secrets?: boolean }>) => {
            e.stopPropagation();
            this._includeSecrets = !!e.detail.value.include_secrets;
          }}
        ></ha-form>
        ${this._includeSecrets
          ? html`<ha-alert alert-type="warning">Keep the file private – it contains credentials in plain text.</ha-alert>`
          : nothing}
      `,
      primary: html`<ha-button slot="primaryAction" .loading=${busy} ?disabled=${busy} @click=${this._export}>
        Download
      </ha-button>`,
    };
  }

  private _copyDialog(busy: boolean, keysOk: boolean): DialogContent {
    const others = this.devices.filter((d) => isLoaded(d) && d.entry_id !== this.entryId);
    const schema: HaFormSchema[] = [
      {
        name: "targets",
        selector: {
          select: {
            multiple: true,
            mode: "list",
            options: others.map((d) => ({ value: d.entry_id, label: `${d.name}${d.available ? "" : " (offline)"}` })),
          },
        },
      },
    ];
    return {
      title: "Copy settings to other displays",
      body: html`
        <div class="stack">
          ${this._editCount
            ? html`<ha-alert alert-type="warning">Unsaved changes are not copied – save them first.</ha-alert>`
            : nothing}
          ${others.length
            ? html`<ha-form
                .hass=${this.page.hass}
                .data=${{ targets: this._targets }}
                .schema=${schema}
                .computeLabel=${() => "Target displays"}
                @value-changed=${(e: ValueChangedEvent<{ targets?: string[] }>) => {
                  e.stopPropagation();
                  this._targets = e.detail.value.targets ?? [];
                }}
              ></ha-form>`
            : html`<ha-alert alert-type="info">There are no other displays.</ha-alert>`}
          ${this._renderKeysChoice()}
        </div>
      `,
      primary: html`<ha-button
        slot="primaryAction"
        .loading=${busy}
        ?disabled=${busy || !this._targets.length || !keysOk}
        @click=${this._copy}
      >
        Copy
      </ha-button>`,
    };
  }

  private _profileDialog(busy: boolean, keysOk: boolean): DialogContent {
    const schema: HaFormSchema[] = [
      { name: "name", required: true, selector: { text: {} } },
      { name: "make_default", selector: { boolean: {} } },
    ];
    return {
      title: "Save as profile",
      body: html`
        <div class="stack">
          <ha-form
            .hass=${this.page.hass}
            .data=${{ name: this._profileName, make_default: this._profileDefault }}
            .schema=${schema}
            .computeLabel=${(s: HaFormSchema) => (s.name === "name" ? "Profile name" : "Default profile for new displays")}
            @value-changed=${(e: ValueChangedEvent<{ name?: string; make_default?: boolean }>) => {
              e.stopPropagation();
              this._profileName = e.detail.value.name ?? "";
              this._profileDefault = !!e.detail.value.make_default;
            }}
          ></ha-form>
          ${this._editCount
            ? html`<ha-alert alert-type="info">
                Your ${plural(this._editCount, "unsaved change")} are included in the profile.
              </ha-alert>`
            : nothing}
          ${this._renderKeysChoice()}
        </div>
      `,
      primary: html`<ha-button
        slot="primaryAction"
        .loading=${busy}
        ?disabled=${busy || !this._profileName.trim() || !keysOk}
        @click=${this._saveProfile}
      >
        Save profile
      </ha-button>`,
    };
  }

  private _dialogContent(which: Dialog): DialogContent | null {
    const busy = this._dialogBusy;
    const keysOk = this._keysMode === "all" || this._keys.size > 0;
    switch (which) {
      case "export":
        return this._exportDialog(busy);
      case "copy":
        return this._copyDialog(busy, keysOk);
      case "profile":
        return this._profileDialog(busy, keysOk);
      default:
        return null;
    }
  }

  private _renderDialog() {
    const content = this._dialogContent(this._dialog || this._openDialogName);
    const busy = this._dialogBusy;
    return html`
      <ha-dialog
        .open=${this._dialog !== ""}
        width="medium"
        .headerTitle=${content?.title ?? ""}
        .preventScrimClose=${busy}
        @closed=${this._dialogClosed}
      >
        ${content?.body ?? nothing}
        <ha-dialog-footer slot="footer">
          <ha-button slot="secondaryAction" appearance="plain" ?disabled=${busy} @click=${this._closeDialog}>Cancel</ha-button>
          ${content?.primary ?? nothing}
        </ha-dialog-footer>
      </ha-dialog>
    `;
  }

  // ------------------------------------------------------------------ rendering: page

  private _renderContent() {
    return html`
      ${this._error
        ? html`<ha-alert alert-type="error" title="Could not load the settings">
            ${this._error}
            <ha-button slot="action" appearance="plain" @click=${this._load}>Retry</ha-button>
          </ha-alert>`
        : nothing}
      ${this._renderEditor()}
    `;
  }

  /** Save FAB that appears with unsaved changes (as in HA's editors). */
  private _fab() {
    if (!this._dirty) return nothing;
    return html`<ha-button
      slot="fab"
      size="l"
      .loading=${this._saving}
      ?disabled=${this._saving || this._loading || !this._editCount || this._blockingInvalid.length > 0}
      @click=${this._save}
    >
      <ha-svg-icon slot="start" .path=${mdiContentSave}></ha-svg-icon>Save
    </ha-button>`;
  }

  render() {
    if (!this.page) return nothing;
    const content = this.devices.some(isLoaded)
      ? html`${this._renderSearch()}<div class="content">${this._renderContent()}</div>`
      : html`<div class="content">${noDisplaysCard(this, this.devices)}</div>`;
    return html`
      ${renderPage(this, this.page, content, this._fab(), this._menu())}
      ${this._renderDialog()}
    `;
  }

  static styles = [
    sharedStyles,
    pageStyles,
    dialogStyles,
    css`
      /* controls at the end of a row: ha-backup-config-schedule */
      .end {
        display: flex;
        align-items: center;
      }
      .end ha-select {
        min-width: 210px;
      }
      .end ha-input {
        width: 210px;
        /* no space reserved for a hint (errors are shown in the supporting text): 56px like ha-select */
        --ha-input-padding-bottom: 0;
      }
      /* below the sticky search bar the cards start 16px down, as on Settings → System → Logs */
      .search + .content {
        padding-top: var(--ha-space-4);
      }
      @media all and (max-width: 450px) {
        .end ha-select,
        .end ha-input {
          min-width: 160px;
          width: 160px;
        }
      }
      .unit {
        color: var(--secondary-text-color);
      }
      .lock {
        font-style: italic;
      }
      .unavailable [slot="headline"] {
        color: var(--disabled-text-color);
      }
      /* collapsed cards: the panel header takes the place of the card header */
      ha-expansion-panel.collapsed {
        --expansion-panel-summary-padding: var(--ha-space-2) var(--ha-space-4);
        --expansion-panel-content-padding: 0;
      }
      ha-form + ha-alert,
      ha-form + sep-key-picker {
        margin-top: var(--ha-space-2);
      }
    `,
  ];
}

define("sep-settings-tab", SeSettingsTab);

declare global {
  interface HTMLElementTagNameMap {
    "sep-settings-tab": SeSettingsTab;
  }
}
