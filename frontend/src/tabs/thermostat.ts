import { LitElement, type PropertyValues, css, html, nothing } from "lit";
import { mdiContentSave, mdiDelete, mdiPlus } from "@mdi/js";
import {
  type DeviceSummary,
  type ElevateApi,
  type ScheduleGetResult,
  type SwitchPoint,
  type ThermostatOptions,
  type ThermostatOptionsResult,
  WEEKDAYS,
  type WeekSchedule,
  type Weekday,
  errorMessage,
  isLoaded,
} from "../api";
import type { HaFormSchema, ValueChangedEvent } from "../ha";
import { type PageContext, displayPicker, noDisplaysCard, pageStyles, renderPage } from "../page";
import { sharedStyles } from "../styles";
import { confirmDialog, define, refreshDevices, selectEntry, toast, toastError } from "../ui";

interface OptionsForm extends ThermostatOptions {
  enabled: boolean;
}

const OPTION_LABELS: Record<string, string> = {
  enabled: "Thermostat",
  thermostat_relay: "Relay",
  thermostat_sensor: "Temperature sensor",
  thermostat_mode: "Mode",
  thermostat_tolerance: "Tolerance",
  thermostat_min_cycle: "Minimum cycle time",
  thermostat_min_temp: "Minimum target temperature",
  thermostat_max_temp: "Maximum target temperature",
};
const OPTION_HELPERS: Record<string, string> = {
  enabled: "Creates a thermostat entity that switches a relay of the display based on the temperature.",
  thermostat_sensor: "Leave empty to use the display's own sensor.",
  thermostat_tolerance: "The relay switches at target temperature ± tolerance.",
  thermostat_min_cycle: "Minimum time between two switching operations (0 = off).",
};

const DAY_LABELS: Record<Weekday, string> = {
  mon: "Monday",
  tue: "Tuesday",
  wed: "Wednesday",
  thu: "Thursday",
  fri: "Friday",
  sat: "Saturday",
  sun: "Sunday",
};
const WORKDAYS: Weekday[] = ["mon", "tue", "wed", "thu", "fri"];
const MAX_POINTS = 12;

const clone = (schedule: WeekSchedule): WeekSchedule =>
  Object.fromEntries(WEEKDAYS.map((d) => [d, schedule[d].map((p) => ({ ...p }))])) as WeekSchedule;

const sorted = (points: SwitchPoint[]): SwitchPoint[] => [...points].sort((a, b) => a.time.localeCompare(b.time));

/** Weekly schedule of the thermostats: switch points per day, followed in auto mode. */
export class SeThermostatTab extends LitElement {
  static properties = {
    page: { attribute: false },
    api: { attribute: false },
    devices: { attribute: false },
    entryId: {},
    narrow: { type: Boolean, reflect: true },
    _options: { state: true },
    _form: { state: true },
    _savingOptions: { state: true },
    _data: { state: true },
    _draft: { state: true },
    _loading: { state: true },
    _saving: { state: true },
    _error: { state: true },
  };

  declare page: PageContext;
  declare api: ElevateApi;
  declare devices: DeviceSummary[];
  declare entryId: string;
  declare narrow: boolean;
  declare _options: ThermostatOptionsResult | null;
  declare _form: OptionsForm | null;
  declare _savingOptions: boolean;
  declare _data: ScheduleGetResult | null;
  declare _draft: WeekSchedule | null;
  declare _loading: boolean;
  declare _saving: boolean;
  declare _error: string;

  private _loadedFor = "";

  constructor() {
    super();
    this.narrow = false;
    this.devices = [];
    this.entryId = "";
    this._options = null;
    this._form = null;
    this._savingOptions = false;
    this._data = null;
    this._draft = null;
    this._loading = false;
    this._saving = false;
    this._error = "";
  }

  protected willUpdate(changed: PropertyValues<this>): void {
    if ((changed.has("entryId") || changed.has("api") || changed.has("devices")) && this.api) {
      const loaded = this.devices.filter(isLoaded);
      if (!this.entryId && loaded.length) {
        // same display as the other tabs: pick the first one for all of them
        selectEntry(this, loaded[0].entry_id);
        return;
      }
      if (this.entryId && this.entryId !== this._loadedFor && loaded.some((d) => d.entry_id === this.entryId)) {
        this._load();
      }
    }
  }

  private get _dirty(): boolean {
    return !!this._draft && !!this._data && JSON.stringify(this._draft) !== JSON.stringify(this._data.schedule);
  }

  private async _load(): Promise<void> {
    const entryId = this.entryId;
    this._loadedFor = entryId;
    this._loading = true;
    this._error = "";
    try {
      const options = await this.api.thermostatOptionsGet(entryId);
      const data = options.enabled ? await this.api.scheduleGet(entryId) : null;
      if (entryId !== this.entryId) return;
      this._options = options;
      this._form = { enabled: options.enabled, ...options.options, thermostat_sensor: options.options.thermostat_sensor ?? "" };
      this._data = data;
      this._draft = data ? clone(data.schedule) : null;
    } catch (err) {
      this._error = errorMessage(err);
      this._options = null;
      this._form = null;
      this._data = null;
      this._draft = null;
    } finally {
      this._loading = false;
    }
  }

  private get _formDirty(): boolean {
    if (!this._form || !this._options) return false;
    const saved: OptionsForm = { enabled: this._options.enabled, ...this._options.options, thermostat_sensor: this._options.options.thermostat_sensor ?? "" };
    return JSON.stringify(this._form) !== JSON.stringify(saved);
  }

  private async _select(entryId: string): Promise<void> {
    if (entryId === this.entryId) return;
    if (this._dirty || this._formDirty) {
      const ok = await confirmDialog(this, {
        title: "Discard unsaved changes?",
        text: "The changed thermostat settings or schedule will be lost.",
        confirmText: "Discard",
        destructive: true,
      });
      if (!ok) return;
    }
    selectEntry(this, entryId);
  }

  private async _saveOptions(): Promise<void> {
    if (!this._form) return;
    const { enabled, ...options } = this._form;
    this._savingOptions = true;
    try {
      const result = await this.api.thermostatOptionsSet(this.entryId, enabled, enabled ? options : undefined);
      if (result.changed) {
        toast(this, enabled ? "Thermostat settings saved. The display reloads." : "Thermostat turned off. The display reloads.");
        // the display reloads with the new options; give it a moment before reading them back
        await new Promise((resolve) => setTimeout(resolve, 2500));
        refreshDevices(this);
        this._loadedFor = "";
        await this._load();
      }
    } catch (err) {
      toastError(this, "Could not save the thermostat settings", err);
    } finally {
      this._savingOptions = false;
    }
  }

  private _update(day: Weekday, points: SwitchPoint[]): void {
    if (!this._draft) return;
    this._draft = { ...this._draft, [day]: points };
  }

  private _setPoint(day: Weekday, index: number, change: Partial<SwitchPoint>): void {
    const points = this._draft![day].map((p, i) => (i === index ? { ...p, ...change } : p));
    this._update(day, points);
  }

  private _addPoint(day: Weekday): void {
    const points = this._draft![day];
    const last = points[points.length - 1];
    const hour = last ? Math.min(23, Number(last.time.slice(0, 2)) + 1) : 6;
    this._update(day, [...points, { time: `${String(hour).padStart(2, "0")}:00`, temperature: last?.temperature ?? 21 }]);
  }

  private _copy(from: Weekday, to: Weekday[]): void {
    if (!this._draft) return;
    const next = { ...this._draft };
    for (const day of to) next[day] = this._draft[from].map((p) => ({ ...p }));
    this._draft = next;
  }

  private _problems(): string[] {
    if (!this._draft) return [];
    const problems: string[] = [];
    for (const day of WEEKDAYS) {
      const times = this._draft[day].map((p) => p.time);
      if (new Set(times).size !== times.length) problems.push(`${DAY_LABELS[day]}: a time appears twice`);
      if (this._draft[day].some((p) => !/^([01]\d|2[0-3]):[0-5]\d$/.test(p.time))) problems.push(`${DAY_LABELS[day]}: invalid time`);
      if (this._draft[day].some((p) => !Number.isFinite(p.temperature))) problems.push(`${DAY_LABELS[day]}: invalid temperature`);
    }
    return problems;
  }

  private async _save(): Promise<void> {
    if (!this._draft) return;
    const problems = this._problems();
    if (problems.length) {
      toast(this, "The schedule cannot be saved", "error", problems);
      return;
    }
    this._saving = true;
    try {
      const draft = Object.fromEntries(WEEKDAYS.map((d) => [d, sorted(this._draft![d])])) as WeekSchedule;
      await this.api.scheduleSet(this.entryId, draft);
      this._data = await this.api.scheduleGet(this.entryId);
      this._draft = clone(this._data.schedule);
      toast(this, "Schedule saved");
    } catch (err) {
      toastError(this, "Could not save the schedule", err);
    } finally {
      this._saving = false;
    }
  }

  private _renderDay(day: Weekday) {
    const points = this._draft![day];
    return html`<div class="day">
      <div class="day-head">
        <span class="day-name">${DAY_LABELS[day]}</span>
        <span class="day-actions">
          ${day === "mon"
            ? html`<ha-button appearance="plain" size="s" @click=${() => this._copy("mon", WORKDAYS.slice(1))}>Copy to Tue–Fri</ha-button>`
            : nothing}
          ${day === "sat" ? html`<ha-button appearance="plain" size="s" @click=${() => this._copy("sat", ["sun"])}>Copy to Sun</ha-button>` : nothing}
        </span>
      </div>
      <div class="points">
        ${points.length
          ? points.map(
              (p, i) => html`<div class="point">
                <input
                  type="time"
                  .value=${p.time}
                  aria-label="Time"
                  @change=${(e: Event) => this._setPoint(day, i, { time: (e.target as HTMLInputElement).value })}
                />
                <input
                  type="number"
                  step="0.5"
                  min="5"
                  max="30"
                  .value=${String(p.temperature)}
                  aria-label="Temperature"
                  @change=${(e: Event) => this._setPoint(day, i, { temperature: Number((e.target as HTMLInputElement).value) })}
                /><span class="unit">°C</span>
                <ha-icon-button
                  .path=${mdiDelete}
                  label="Remove"
                  @click=${() => this._update(day, points.filter((_, j) => j !== i))}
                ></ha-icon-button>
              </div>`,
            )
          : html`<span class="secondary">No switch point: the last target of an earlier day holds.</span>`}
        ${points.length < MAX_POINTS
          ? html`<ha-icon-button class="add" .path=${mdiPlus} label="Add switch point" @click=${() => this._addPoint(day)}></ha-icon-button>`
          : nothing}
      </div>
    </div>`;
  }

  private _optionsSchema(): HaFormSchema[] {
    const o = this._options!;
    const schema: HaFormSchema[] = [{ name: "enabled", selector: { boolean: {} } }];
    if (!this._form?.enabled) return schema;
    return [
      ...schema,
      {
        name: "thermostat_relay",
        required: true,
        selector: {
          select: {
            mode: "dropdown",
            options: Array.from({ length: Math.max(1, o.relays) }, (_, i) => ({ value: String(i), label: `${i + 1}` })),
          },
        },
      },
      {
        name: "thermostat_sensor",
        required: !o.own_sensor,
        selector: { entity: { filter: { domain: "sensor", device_class: "temperature" } } },
      },
      {
        name: "thermostat_mode",
        required: true,
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: "heat", label: "Heat" },
              { value: "cool", label: "Cool" },
            ],
          },
        },
      },
      { name: "thermostat_tolerance", required: true, selector: { number: { min: 0.1, max: 3, step: 0.1, mode: "box", unit_of_measurement: "°C" } } },
      { name: "thermostat_min_cycle", required: true, selector: { number: { min: 0, max: 86400, step: 10, mode: "box", unit_of_measurement: "s" } } },
      { name: "thermostat_min_temp", required: true, selector: { number: { min: -10, max: 40, step: 0.5, mode: "box", unit_of_measurement: "°C" } } },
      { name: "thermostat_max_temp", required: true, selector: { number: { min: 0, max: 50, step: 0.5, mode: "box", unit_of_measurement: "°C" } } },
    ];
  }

  private _renderOptions() {
    const o = this._options;
    if (!o || !this._form) return nothing;
    if (!o.relays)
      return html`<ha-card header="Thermostat"><div class="card-content">
        <p>This display has no relay to switch, so it cannot be a thermostat.</p>
      </div></ha-card>`;
    return html`<ha-card>
      <div class="card-header">
        <span>Thermostat</span>
        ${displayPicker(this.page.hass, this.devices, this.entryId, (entryId) => this._select(entryId))}
      </div>
      <div class="card-content">
        <ha-form
          .hass=${this.page.hass}
          .data=${this._form}
          .schema=${this._optionsSchema()}
          .disabled=${this._savingOptions}
          .computeLabel=${(schema: HaFormSchema) => OPTION_LABELS[schema.name] ?? schema.name}
          .computeHelper=${(schema: HaFormSchema) => OPTION_HELPERS[schema.name] ?? ""}
          @value-changed=${(e: ValueChangedEvent<OptionsForm>) => {
            e.stopPropagation();
            this._form = { ...this._form!, ...e.detail.value };
          }}
        ></ha-form>
        <div class="card-actions-row">
          ${o.entity_id ? html`<span class="secondary">${o.entity_id}</span>` : html`<span></span>`}
          <ha-button .loading=${this._savingOptions} ?disabled=${!this._formDirty || this._savingOptions} @click=${this._saveOptions}>
            Save settings
          </ha-button>
        </div>
      </div>
    </ha-card>`;
  }

  private _renderSchedule() {
    const data = this._data;
    if (!this._options?.enabled || !data || !this._draft) return nothing;
    const next = data.next_change ? new Date(data.next_change) : null;
    return html`<ha-card header="Weekly schedule">
      <div class="card-content">
        <p class="secondary">
          The thermostat follows this schedule in <b>auto</b> mode. A switch point holds until the next one; a target set by hand
          holds until the next switch point.
        </p>
        <p>
          Now: <b>${data.current_temperature ?? "–"} °C</b>${next
            ? html` · next change ${next.toLocaleString(undefined, { weekday: "short", hour: "2-digit", minute: "2-digit" })}`
            : nothing}${data.default ? html` · <span class="secondary">built-in default</span>` : nothing}
        </p>
        ${WEEKDAYS.map((d) => this._renderDay(d))}
      </div>
    </ha-card>`;
  }

  private _renderContent() {
    if (!this.devices.some(isLoaded)) return noDisplaysCard(this, this.devices);
    if (this._loading && !this._options) return html`<div class="loading"><ha-spinner></ha-spinner></div>`;
    return html`
      ${this._error ? html`<ha-alert alert-type="error" title="Could not load the thermostat">${this._error}</ha-alert>` : nothing}
      ${this._renderOptions()} ${this._renderSchedule()}
    `;
  }

  render() {
    if (!this.page) return nothing;
    const fab = this._draft && this._options?.enabled
      ? html`<ha-button slot="fab" size="l" .loading=${this._saving} ?disabled=${!this._dirty || this._saving} @click=${this._save}>
          <ha-svg-icon slot="start" .path=${mdiContentSave}></ha-svg-icon>Save schedule
        </ha-button>`
      : nothing;
    return renderPage(this, this.page, html`<div class="content">${this._renderContent()}</div>`, fab, {
      onReload: () => {
        this._loadedFor = "";
        this._load();
      },
    });
  }

  static styles = [
    sharedStyles,
    pageStyles,
    css`
      ha-card + ha-card {
        margin-top: var(--ha-space-4);
      }
      .card-actions-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--ha-space-2);
        margin-top: var(--ha-space-4);
      }
      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--ha-space-2);
      }
      input {
        font: inherit;
        color: var(--primary-text-color);
        background: var(--card-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 6px;
        padding: 4px 6px;
      }
      .day {
        border-top: 1px solid var(--divider-color);
        padding: var(--ha-space-2) 0;
      }
      .day-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-height: 36px;
      }
      .day-name {
        font-weight: 500;
      }
      .points {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--ha-space-2);
      }
      .point {
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 2px 2px 2px 8px;
        border-radius: 18px;
        background: var(--secondary-background-color);
      }
      .point input[type="number"] {
        width: 4.5em;
      }
      .unit {
        color: var(--secondary-text-color);
      }
      .secondary {
        color: var(--secondary-text-color);
      }
      .loading {
        display: flex;
        justify-content: center;
        padding: var(--ha-space-6);
      }
    `,
  ];
}

define("sep-thermostat-tab", SeThermostatTab);
