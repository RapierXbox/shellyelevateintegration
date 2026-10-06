import { LitElement, css, html, nothing } from "lit";
import { type DeviceSummary, type DiffItem, ElevateApi, type Profile, deviceName, errorMessage, isLoaded } from "../api";
import { type HaFormSchema, type ValueChangedEvent, onDialogClosed } from "../ha";
import { dialogStyles, sharedStyles } from "../styles";
import { define, plural, toast } from "../ui";
import "./diff-table";

type Stage = "select" | "preview" | "applying";

interface ApplyForm {
  profile: string;
  displays: string[];
}

/** Dry-run result per display: the diff, or why it could not be computed. */
type Preview = Record<string, DiffItem[] | { error: string }>;

const hasChanges = (result: Preview[string]): result is DiffItem[] => Array.isArray(result) && result.length > 0;

/**
 * Apply a profile to displays: pick profile + displays → dry-run diff per display → apply.
 * Call `show(profileId?, entryIds?)`. Fires `applied` when done.
 */
export class SeApplyProfileDialog extends LitElement {
  static properties = {
    api: { attribute: false },
    devices: { attribute: false },
    profiles: { attribute: false },
    _open: { state: true },
    _stage: { state: true },
    _data: { state: true },
    _preview: { state: true },
    _busy: { state: true },
    _error: { state: true },
  };

  declare api: ElevateApi;
  declare devices: DeviceSummary[];
  declare profiles: Profile[];
  declare _open: boolean;
  declare _stage: Stage;
  declare _data: ApplyForm;
  declare _preview: Preview;
  declare _busy: boolean;
  declare _error: string;

  constructor() {
    super();
    this.devices = [];
    this.profiles = [];
    this._open = false;
    this._stage = "select";
    this._data = { profile: "", displays: [] };
    this._preview = {};
    this._busy = false;
    this._error = "";
  }

  show(profileId?: string, entryIds?: string[]): void {
    const def = this.profiles.find((p) => p.default)?.id ?? this.profiles[0]?.id ?? "";
    this._data = { profile: profileId ?? def, displays: entryIds ?? [] };
    this._stage = "select";
    this._preview = {};
    this._error = "";
    this._busy = false;
    this._open = true;
  }

  private _close(): void {
    if (this._stage === "applying") return;
    this._open = false;
  }

  private _closed = onDialogClosed(() => (this._open = false));

  private get _profileName(): string {
    return this.profiles.find((p) => p.id === this._data.profile)?.name ?? "";
  }

  /** Dry run: the diff per display, or why it could not be computed. */
  private async _previewChanges(): Promise<void> {
    this._busy = true;
    this._error = "";
    try {
      const { results, errors } = await this.api.profilesApply(this._data.profile, this._data.displays, true);
      const out: Preview = {};
      for (const entryId of this._data.displays) {
        out[entryId] = entryId in errors ? { error: errors[entryId] } : (results[entryId] ?? []);
      }
      this._preview = out;
      this._stage = "preview";
    } catch (err) {
      this._error = errorMessage(err);
    } finally {
      this._busy = false;
    }
  }

  private async _apply(): Promise<void> {
    const targets = Object.entries(this._preview)
      .filter(([, v]) => hasChanges(v))
      .map(([k]) => k);
    if (!targets.length) return;
    this._stage = "applying";
    this._error = "";
    try {
      const { results, errors } = await this.api.profilesApply(this._data.profile, targets, false);
      const applied = targets.filter((id) => id in results && !(id in errors));
      const failed = targets.filter((id) => id in errors || !(id in results));
      if (!applied.length) {
        // nothing was changed: stay in the dialog and show why
        this._error = failed.map((id) => `${deviceName(this.devices, id)}: ${errors[id] ?? "failed"}`).join("\n");
        this._stage = "preview";
        return;
      }
      const changed = applied.reduce((n, id) => n + (results[id]?.length ?? 0), 0);
      const profile = `Profile “${this._profileName}”`;
      if (failed.length) {
        toast(
          this,
          `${profile} applied to ${applied.length} of ${plural(targets.length, "display")}`,
          "warning",
          failed.map((id) => `${deviceName(this.devices, id)}: ${errors[id] ?? "failed"}`),
        );
      } else {
        toast(this, `${profile} applied to ${plural(applied.length, "display")} (${plural(changed, "setting")} changed)`, "success");
      }
      this._open = false;
      this.dispatchEvent(new CustomEvent("applied"));
    } catch (err) {
      this._error = errorMessage(err);
      this._stage = "preview";
    }
  }

  private _renderSelect() {
    const loaded = this.devices.filter(isLoaded);
    const schema: HaFormSchema[] = [
      {
        name: "profile",
        required: true,
        selector: {
          select: {
            mode: "dropdown",
            options: this.profiles.map((p) => ({ value: p.id, label: `${p.name}${p.default ? " (default)" : ""}` })),
          },
        },
      },
      {
        name: "displays",
        selector: {
          select: {
            multiple: true,
            mode: "list",
            options: loaded.map((d) => ({
              value: d.entry_id,
              label: `${d.name}${d.available ? "" : " (offline)"}`,
            })),
          },
        },
      },
    ];
    return html`
      <ha-form
        .hass=${this.api.hass}
        .data=${this._data}
        .schema=${schema}
        .computeLabel=${(s: HaFormSchema) => (s.name === "profile" ? "Profile" : "Displays")}
        @value-changed=${(e: ValueChangedEvent<Partial<ApplyForm>>) => {
          e.stopPropagation();
          this._data = { profile: e.detail.value.profile ?? "", displays: e.detail.value.displays ?? [] };
        }}
      ></ha-form>
      ${loaded.length ? nothing : html`<ha-alert alert-type="info">No displays are set up.</ha-alert>`}
      <p class="secondary note">
        Per-display settings (IDs, names) are never applied. A backup of each display is taken before it is changed.
      </p>
    `;
  }

  private _renderPreview() {
    const entries = Object.entries(this._preview);
    const changing = entries.filter(([, v]) => hasChanges(v)).length;
    const total = entries.reduce((n, [, v]) => n + (Array.isArray(v) ? v.length : 0), 0);
    return html`
      <ha-alert alert-type=${changing ? "info" : "success"}>
        ${changing
          ? html`Applying <b>${this._profileName}</b> changes ${plural(total, "setting")} on ${plural(changing, "display")}.`
          : html`All selected displays already match <b>${this._profileName}</b>.`}
      </ha-alert>
      <div class="panels">
        ${entries.map(([entryId, result]) => {
          const isErr = !Array.isArray(result);
          const secondary = isErr ? "Error" : result.length ? plural(result.length, "change") : "Up to date";
          return html`
            <ha-expansion-panel
              outlined
              .header=${deviceName(this.devices, entryId)}
              .secondary=${secondary}
              .expanded=${isErr || result.length > 0}
            >
              ${isErr
                ? html`<ha-alert alert-type="error">${result.error}</ha-alert>`
                : html`<sep-diff-table .diff=${result}></sep-diff-table>`}
            </ha-expansion-panel>
          `;
        })}
      </div>
    `;
  }

  private _renderFooter() {
    if (this._stage === "select") {
      return html`
        <ha-button slot="secondaryAction" appearance="plain" @click=${this._close}>Cancel</ha-button>
        <ha-button
          slot="primaryAction"
          .loading=${this._busy}
          ?disabled=${!this._data.profile || !this._data.displays.length || this._busy}
          @click=${this._previewChanges}
          >Preview changes</ha-button
        >
      `;
    }
    const applying = this._stage === "applying";
    const canApply = Object.values(this._preview).some(hasChanges);
    return html`
      <ha-button slot="secondaryAction" appearance="plain" ?disabled=${applying} @click=${() => (this._stage = "select")}
        >Back</ha-button
      >
      <ha-button slot="primaryAction" .loading=${applying} ?disabled=${!canApply || applying} @click=${this._apply}
        >Apply to displays</ha-button
      >
    `;
  }

  render() {
    return html`
      <ha-dialog
        .open=${this._open}
        width="large"
        header-title="Apply profile"
        .headerSubtitle=${this._stage === "select" ? undefined : this._profileName}
        .preventScrimClose=${this._stage === "applying" || this._busy}
        @closed=${this._closed}
      >
        ${this._error
          ? html`<ha-alert alert-type="error" class="error-alert" title="Could not apply the profile"
              ><span class="pre">${this._error}</span></ha-alert
            >`
          : nothing}
        ${this._stage === "select" ? this._renderSelect() : this._renderPreview()}
        <ha-dialog-footer slot="footer">${this._renderFooter()}</ha-dialog-footer>
      </ha-dialog>
    `;
  }

  static styles = [
    sharedStyles,
    dialogStyles,
    css`
      .note {
        margin-top: var(--ha-space-4);
        font-size: var(--ha-font-size-s);
      }
      .error-alert {
        margin-bottom: var(--ha-space-4);
      }
      .pre {
        white-space: pre-line;
      }
      .panels {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-2);
        margin-top: var(--ha-space-4);
      }
      ha-expansion-panel {
        --expansion-panel-content-padding: 0 var(--ha-space-4);
      }
    `,
  ];
}

define("sep-apply-profile-dialog", SeApplyProfileDialog);

declare global {
  interface HTMLElementTagNameMap {
    "sep-apply-profile-dialog": SeApplyProfileDialog;
  }
}
