import { LitElement, type PropertyValues, css, html, nothing } from "lit";
import { mdiContentSave, mdiDelete, mdiPlus } from "@mdi/js";
import {
  type ElevateApi,
  type ScheduleGetResult,
  type SwitchPoint,
  type ThermostatSummary,
  WEEKDAYS,
  type WeekSchedule,
  type Weekday,
  errorMessage,
} from "../api";
import { type PageContext, pageStyles, renderPage } from "../page";
import { sharedStyles } from "../styles";
import { confirmDialog, define, toast, toastError } from "../ui";

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
    narrow: { type: Boolean, reflect: true },
    _thermostats: { state: true },
    _entryId: { state: true },
    _data: { state: true },
    _draft: { state: true },
    _loading: { state: true },
    _saving: { state: true },
    _error: { state: true },
  };

  declare page: PageContext;
  declare api: ElevateApi;
  declare narrow: boolean;
  declare _thermostats: ThermostatSummary[];
  declare _entryId: string;
  declare _data: ScheduleGetResult | null;
  declare _draft: WeekSchedule | null;
  declare _loading: boolean;
  declare _saving: boolean;
  declare _error: string;

  private _loadedOnce = false;

  constructor() {
    super();
    this.narrow = false;
    this._thermostats = [];
    this._entryId = "";
    this._data = null;
    this._draft = null;
    this._loading = false;
    this._saving = false;
    this._error = "";
  }

  protected willUpdate(changed: PropertyValues<this>): void {
    if (changed.has("api") && this.api && !this._loadedOnce) {
      this._loadedOnce = true;
      this._loadThermostats();
    }
  }

  private get _dirty(): boolean {
    return !!this._draft && !!this._data && JSON.stringify(this._draft) !== JSON.stringify(this._data.schedule);
  }

  private async _loadThermostats(): Promise<void> {
    this._loading = true;
    this._error = "";
    try {
      this._thermostats = await this.api.thermostats();
      const first = this._thermostats.find((t) => t.loaded);
      if (!this._entryId && first) this._entryId = first.entry_id;
      if (this._entryId) await this._loadSchedule();
    } catch (err) {
      this._error = errorMessage(err);
    } finally {
      this._loading = false;
    }
  }

  private async _loadSchedule(): Promise<void> {
    this._loading = true;
    this._error = "";
    try {
      this._data = await this.api.scheduleGet(this._entryId);
      this._draft = clone(this._data.schedule);
    } catch (err) {
      this._error = errorMessage(err);
      this._data = null;
      this._draft = null;
    } finally {
      this._loading = false;
    }
  }

  private async _select(entryId: string): Promise<void> {
    if (entryId === this._entryId) return;
    if (this._dirty) {
      const ok = await confirmDialog(this, {
        title: "Discard unsaved changes?",
        text: "The changed schedule will be lost.",
        confirmText: "Discard",
        destructive: true,
      });
      if (!ok) return;
    }
    this._entryId = entryId;
    await this._loadSchedule();
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
      await this.api.scheduleSet(this._entryId, draft);
      await this._loadSchedule();
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

  private _renderContent() {
    if (this._loading && !this._thermostats.length) return html`<div class="loading"><ha-spinner></ha-spinner></div>`;
    if (!this._thermostats.length)
      return html`<ha-alert alert-type="info" title="No thermostat yet">
        Turn on “Create a thermostat” in the options of a display to give it a weekly schedule.
      </ha-alert>`;
    const data = this._data;
    const next = data?.next_change ? new Date(data.next_change) : null;
    return html`
      ${this._error ? html`<ha-alert alert-type="error" title="Could not load the schedule">${this._error}</ha-alert>` : nothing}
      <ha-card>
        <div class="card-header">
          <span>Weekly schedule</span>
          <select .value=${this._entryId} @change=${(e: Event) => this._select((e.target as HTMLSelectElement).value)}>
            ${this._thermostats.map(
              (t) => html`<option value=${t.entry_id} ?disabled=${!t.loaded} ?selected=${t.entry_id === this._entryId}>${t.name}</option>`,
            )}
          </select>
        </div>
        <div class="card-content">
          <p class="secondary">
            The thermostat follows this schedule in <b>auto</b> mode. A switch point holds until the next one; a target set by
            hand holds until the next switch point.
          </p>
          ${data
            ? html`<p>
                Now: <b>${data.current_temperature ?? "–"} °C</b>${next
                  ? html` · next change ${next.toLocaleString(undefined, { weekday: "short", hour: "2-digit", minute: "2-digit" })}`
                  : nothing}${data.default ? html` · <span class="secondary">built-in default</span>` : nothing}
              </p>`
            : nothing}
          ${this._draft ? WEEKDAYS.map((d) => this._renderDay(d)) : nothing}
        </div>
      </ha-card>
    `;
  }

  render() {
    if (!this.page) return nothing;
    const fab = this._draft
      ? html`<ha-button slot="fab" size="l" .loading=${this._saving} ?disabled=${!this._dirty || this._saving} @click=${this._save}>
          <ha-svg-icon slot="start" .path=${mdiContentSave}></ha-svg-icon>Save
        </ha-button>`
      : nothing;
    return renderPage(this, this.page, html`<div class="content">${this._renderContent()}</div>`, fab, {
      onReload: () => {
        this._loadThermostats();
      },
    });
  }

  static styles = [
    sharedStyles,
    pageStyles,
    css`
      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--ha-space-2);
      }
      select,
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
