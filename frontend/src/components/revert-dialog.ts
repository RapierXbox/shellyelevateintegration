import { LitElement, type PropertyValues, css, html, nothing } from "lit";
import { mdiContentCopy, mdiDownload } from "@mdi/js";
import {
  type DeviceSummary,
  ElevateApi,
  type RevertCheckResult,
  type RevertDoneEvent,
  type RevertEvent,
  type RevertOptions,
  type RevertStepEvent,
  errorMessage,
} from "../api";
import {
  type HaFormSchema,
  type UnsubscribeFunc,
  type ValueChangedEvent,
  copyToClipboard,
  inputValue,
  isChecked,
  isDefined,
  loadProgressBar,
  onDialogClosed,
} from "../ha";
import { dialogStyles, sharedStyles } from "../styles";
import {
  type RevertTarget,
  androidVersion,
  confirmDialog,
  define,
  downloadText,
  plural,
  refreshDevices,
  stopPropagation,
  toast,
} from "../ui";
import type { StepState } from "./step-list";
import "./step-list";
import { type LogLine, commandLine, logText } from "./install-log";
import "./install-log";

// --------------------------------------------------------------------------- static data

const STEP_LABELS: Record<string, string> = {
  adb_connect: "Connect over ADB",
  check: "Check the display",
  mqtt_cleanup: "Remove the MQTT discovery entries",
  stop_app: "Stop Shelly Elevate",
  enable_stock: "Enable the stock Shelly app",
  stock_overlay: "Let the stock Shelly app draw on top again",
  stock_home: "Make the stock Shelly app the home app",
  doze_whitelist: "Remove the battery optimisation exemption",
  app_ops: "Reset the special app permissions",
  brightness_mode: "Restore the brightness mode",
  brightness: "Restore the screen brightness",
  uninstall: "Uninstall Shelly Elevate",
  remove_system_copy: "Remove the copy in /system",
  hide_system_copy: "Hide the copy in /system",
  uninstall_v1: "Uninstall the old Shelly Elevate V1 app",
  uninstall_launcher: "Uninstall Ultra Small Launcher",
  cleanup: "Clean up",
  start_stock: "Start the stock Shelly app",
  verify: "Check the result",
  remove_entry: "Remove from Home Assistant",
  reboot: "Restart the display",
  adb_key: "Remove Home Assistant's ADB key",
  adb_tcp: "Stop ADB on port 5555 after a restart",
  adb_wifi: "Turn off ADB over Wi‑Fi",
  dev_settings: "Turn off the developer settings",
  adb_enabled: "Turn off ADB debugging",
};

/** Order of all steps the backend can report (revert.py / adb/steps.py revert_commands). */
const STEP_ORDER = Object.keys(STEP_LABELS);

/** Steps whose failure stops the revert; the others are reported and the revert goes on. */
const FATAL = new Set(["adb_connect", "check", "remove_entry"]);

const WARNINGS: Record<string, { title: string; text: string; type?: "warning" | "info" }> = {
  wifi_by_app: {
    title: "The display will go offline",
    text: "The display's Wi‑Fi network was set up in Shelly Elevate. Uninstalling the app removes it, and the display loses its connection. To keep it online, set up Wi‑Fi again in the Shelly settings under Network first.",
  },
  stock_needs_root: {
    title: "The stock Shelly app stays disabled",
    text: "It was disabled with root access, and this display is not rooted, so it cannot be enabled again. The display may be left without a home app.",
  },
  system_copy_needs_root: {
    title: "A copy of Shelly Elevate stays in /system",
    text: "It can only be removed on a rooted display. It is hidden and its data is deleted instead.",
  },
  stock_missing: {
    title: "The stock Shelly app is not installed",
    text: "After the revert, the display has no home app.",
  },
  no_baseline: {
    title: "Screen settings stay as they are",
    text: "Shelly Elevate was not installed on this display by this Home Assistant, so the original brightness settings are not known.",
    type: "info",
  },
};

const REMAINING: Record<string, string> = {
  app: "Shelly Elevate is still installed.",
  system_copy: "A copy of Shelly Elevate is still in /system. It can only be removed on a rooted display.",
  stock_disabled: "The stock Shelly app is still disabled. It can only be enabled again on a rooted display.",
};

const OPTION_LABELS: Record<string, [string, string?]> = {
  remove_entry: ["Remove from Home Assistant", "Removes the display and its entities once the app is gone."],
  remove_wiki_launcher: [
    "Remove Ultra Small Launcher",
    "The home app from the community guide. It is removed once the stock Shelly app is the home app again.",
  ],
  reboot: ["Restart the display", "Restarts the display at the end."],
  disable_adb: [
    "Turn off ADB over Wi‑Fi",
    "Turns off ADB debugging and ADB over Wi‑Fi as the very last step. Home Assistant can then no longer reach the display over ADB.",
  ],
};

const REBOOT_WITHOUT_ADB = "Not possible when ADB is turned off: Home Assistant loses ADB access at the end. Restart the display yourself afterwards.";

const FINISHED = new Set<StepState["status"]>(["done", "failed", "warning", "skipped"]);

const HOST_RE = /^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?!$)|$)){4}$|^[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?$/;

const DEFAULT_OPTIONS: RevertOptions = {
  remove_entry: true,
  reboot: true,
  disable_adb: false,
  remove_wiki_launcher: true,
  accept_wifi_loss: false,
};

type Stage = "host" | "checking" | "confirm" | "running" | "done" | "error";

/** The steps the backend is expected to run for these findings and options (revert_commands). */
const expectedSteps = (result: RevertCheckResult, opts: RevertOptions): string[] => {
  const c = result.check;
  const root = result.platform.root;
  const ids = ["adb_connect", "check", "stop_app"];
  if (c.stock_installed) {
    ids.push("enable_stock", "stock_overlay");
    if (c.stock_home) ids.push("stock_home");
  }
  ids.push("doze_whitelist", "app_ops");
  if (c.app_installed) ids.push("uninstall");
  if (c.priv_app || c.init_rc) {
    if (root) ids.push("remove_system_copy");
    else if (c.priv_app) ids.push("hide_system_copy");
  }
  if (c.legacy_v1) ids.push("uninstall_v1");
  if (c.wiki_launcher && opts.remove_wiki_launcher && c.stock_installed) ids.push("uninstall_launcher");
  ids.push("cleanup");
  if (c.stock_installed) ids.push("start_stock");
  ids.push("verify");
  if (result.entry_id && opts.remove_entry) ids.push("remove_entry");
  if (opts.disable_adb) {
    if (root) ids.push("adb_key");
    ids.push("adb_tcp", "adb_wifi", "dev_settings", "adb_enabled");
  } else if (opts.reboot) {
    ids.push("reboot");
  }
  return ids;
};

/** What the revert will do, in plain language (shown before the user confirms). */
const plannedChanges = (result: RevertCheckResult, opts: RevertOptions): string[] => {
  const c = result.check;
  const root = result.platform.root;
  const out: string[] = [];
  if (c.app_installed) out.push("Uninstall Shelly Elevate");
  if (c.priv_app || c.init_rc) {
    out.push(
      root || !c.priv_app
        ? "Remove the copy of Shelly Elevate in /system"
        : "Hide the copy of Shelly Elevate in /system and delete its data",
    );
  }
  if (c.legacy_v1) out.push("Uninstall the old Shelly Elevate V1 app");
  if (c.wiki_launcher && c.stock_installed && opts.remove_wiki_launcher) out.push("Uninstall Ultra Small Launcher");
  // a stock app disabled as root stays disabled without root (see the stock_needs_root warning)
  if (c.stock_installed && !(c.stock_disabled && c.stock_disabled_by_root && !root)) {
    if (c.stock_disabled) out.push("Enable the stock Shelly app again");
    out.push(
      c.stock_home ? "Make the stock Shelly app the home app and start it" : "Let the stock Shelly app draw on top again and start it",
    );
  }
  out.push("Reset the permissions and the battery optimisation exemption Shelly Elevate was given");
  if (!result.warnings.includes("no_baseline")) out.push("Restore the original screen brightness settings");
  if (c.leftover_apk) out.push("Delete the installation file left on the display");
  return out;
};

/** Detail text of a step event (undefined: keep the current detail). */
const stepDetail = (ev: RevertStepEvent, current?: string): string | undefined => {
  if (ev.error) return String(ev.error);
  switch (`${ev.step}:${ev.status}`) {
    case "check:done": {
      const parts = [ev.root === false ? "Not rooted" : ev.root === true ? "Rooted" : "", androidVersion(ev.sdk)];
      return parts.filter(Boolean).join(" · ") || current;
    }
    case "verify:done":
      return "Nothing left";
    case "verify:failed":
      return ev.remaining?.length ? ev.remaining.map((r) => REMAINING[r] ?? r).join(" ") : current;
    case "adb_enabled:done":
      return "The ADB connection was closed";
    default:
      return current;
  }
};

// --------------------------------------------------------------------------- element

/**
 * "Revert to stock": check the display over ADB (read-only), show what would be undone, then run
 * the revert with the installer's step list and log. Lives in the root panel so it survives tab
 * switches; open it with `show()` (the panel does that on `se-revert`).
 */
export class SeRevertDialog extends LitElement {
  static properties = {
    api: { attribute: false },
    devices: { attribute: false },
    _open: { state: true },
    _stage: { state: true },
    _host: { state: true },
    _target: { state: true },
    _check: { state: true },
    _checkError: { state: true },
    _opts: { state: true },
    _steps: { state: true },
    _log: { state: true },
    _error: { state: true },
    _result: { state: true },
    _stepsOpen: { state: true },
    _logOpen: { state: true },
    _hasProgressBar: { state: true },
  };

  declare api: ElevateApi;
  declare devices: DeviceSummary[];
  declare _open: boolean;
  declare _stage: Stage;
  declare _host: string;
  declare _target: RevertTarget;
  declare _check: RevertCheckResult | null;
  declare _checkError: string;
  declare _opts: RevertOptions;
  declare _steps: StepState[];
  declare _log: LogLine[];
  declare _error: string;
  declare _result: RevertDoneEvent | null;
  declare _stepsOpen: boolean;
  declare _logOpen: boolean;
  declare _hasProgressBar: boolean;

  private _unsub: UnsubscribeFunc | null = null;
  private _cancelled = false;
  /** Ignore the result of a check that was superseded (dialog closed or reopened). */
  private _checkSeq = 0;

  constructor() {
    super();
    this.devices = [];
    this._open = false;
    this._stage = "host";
    this._host = "";
    this._target = {};
    this._check = null;
    this._checkError = "";
    this._opts = { ...DEFAULT_OPTIONS };
    this._steps = [];
    this._log = [];
    this._error = "";
    this._result = null;
    this._stepsOpen = false;
    this._logOpen = false;
    this._hasProgressBar = isDefined("ha-progress-bar");
  }

  /** Open the dialog: check `target.host` right away, or ask for the address first. */
  show(target: RevertTarget = {}): void {
    if (this._stage === "running" && this._open) return;
    this._target = target;
    this._host = target.host ?? target.prefill ?? "";
    this._resetRun();
    this._check = null;
    this._checkError = "";
    this._opts = { ...DEFAULT_OPTIONS };
    this._open = true;
    if (target.host) this._runCheck();
    else this._stage = "host";
  }

  protected willUpdate(changed: PropertyValues<this>): void {
    if (changed.has("_open") && this._open && !this._hasProgressBar && this.api) {
      loadProgressBar(this.api.hass, this.renderRoot).then((ok) => (this._hasProgressBar = ok));
    }
  }

  // The revert keeps running when the panel is left: stopping it halfway would leave the display
  // half reverted. Unsubscribing (Cancel) is the only way to stop it.

  private _closed = onDialogClosed(() => {
    this._open = false;
    this._checkSeq++;
  });

  private _close(): void {
    this._open = false;
    this._checkSeq++;
  }

  private get _name(): string {
    return this._check?.name ?? this._target.name ?? this._host;
  }

  private _resetRun(): void {
    this._cancelled = false;
    this._steps = [];
    this._log = [];
    this._error = "";
    this._result = null;
    this._stepsOpen = false;
    this._logOpen = false;
  }

  // ------------------------------------------------------------------ check

  private async _runCheck(): Promise<void> {
    const host = this._host.trim();
    if (!HOST_RE.test(host)) return;
    this._host = host;
    this._stage = "checking";
    this._checkError = "";
    const seq = ++this._checkSeq;
    try {
      const result = await this.api.revertCheck(host);
      if (seq !== this._checkSeq) return;
      this._check = result;
      this._opts = { ...DEFAULT_OPTIONS, remove_entry: !!result.entry_id };
      this._stage = "confirm";
    } catch (err) {
      if (seq !== this._checkSeq) return;
      this._checkError = errorMessage(err);
      this._stage = "confirm";
    }
  }

  // ------------------------------------------------------------------ run

  private async _start(): Promise<void> {
    const check = this._check;
    if (!check) return;
    if (check.warnings.includes("wifi_by_app") && !this._opts.accept_wifi_loss) return;
    this._resetRun();
    this._stage = "running";
    this._steps = expectedSteps(check, this._opts).map((id) => ({ id, label: STEP_LABELS[id] ?? id, status: "pending" }));
    const opts: RevertOptions = {
      ...this._opts,
      remove_entry: !!check.entry_id && this._opts.remove_entry,
      reboot: !this._opts.disable_adb && this._opts.reboot,
      accept_wifi_loss: check.warnings.includes("wifi_by_app") && this._opts.accept_wifi_loss,
    };
    try {
      this._unsub = await this.api.subscribeRevert(this._host, opts, (ev) => this._event(ev));
    } catch (err) {
      this._stage = "error";
      this._error = errorMessage(err);
    }
  }

  private async _stopSubscription(): Promise<void> {
    const unsub = this._unsub;
    this._unsub = null;
    if (unsub) {
      try {
        await unsub();
      } catch {
        // connection already gone
      }
    }
  }

  private async _askCancel(): Promise<void> {
    const ok = await confirmDialog(this, {
      title: "Stop reverting?",
      text: "The running step is stopped. The display may be left partly reverted; you can run the revert again.",
      confirmText: "Stop",
      dismissText: "Keep reverting",
      destructive: true,
    });
    if (!ok || this._stage !== "running") return;
    await this._stopSubscription();
    this._cancelled = true;
    this._addLog({ kind: "error", text: "Cancelled" });
    this._failRunning("Cancelled");
    this._stage = "error";
    this._error = "";
  }

  private _addLog(...lines: LogLine[]): void {
    this._log = [...this._log, ...lines];
  }

  private _failRunning(detail: string): void {
    this._steps = this._steps.map((s) => (s.status === "running" ? { ...s, status: "failed", detail: s.detail || detail } : s));
  }

  /** Index of `id`; steps the expected list does not have are inserted in backend order. */
  private _stepIndex(steps: StepState[], id: string): number {
    const idx = steps.findIndex((s) => s.id === id);
    if (idx >= 0) return idx;
    const rank = STEP_ORDER.indexOf(id);
    let at = steps.findIndex((s) => STEP_ORDER.indexOf(s.id) > rank);
    if (rank < 0 || at < 0) at = steps.length;
    steps.splice(at, 0, { id, label: STEP_LABELS[id] ?? id, status: "pending" });
    return at;
  }

  private _step(ev: RevertStepEvent): void {
    const steps = [...this._steps];
    const idx = this._stepIndex(steps, ev.step);
    const step = steps[idx];
    if (ev.status === "running") {
      this._addLog(ev.command ? commandLine(ev.command) : { kind: "info", text: `# ${step.label}` });
    } else if (ev.status === "failed") {
      this._addLog({ kind: FATAL.has(ev.step) ? "error" : "warning", text: ev.error ? String(ev.error) : stepDetail(ev) ?? "failed" });
    } else if (ev.status === "done") {
      const out = ev.output?.replace(/\r/g, "").trimEnd();
      if (out) this._addLog(...out.split("\n").map((text): LogLine => ({ kind: "output", text })));
    }
    steps[idx] = {
      ...step,
      status: ev.status === "failed" && !FATAL.has(ev.step) ? "warning" : ev.status,
      detail: stepDetail(ev, step.detail),
    };
    if (ev.status === "running") {
      // steps before the current one that never reported were not needed on this display
      for (let i = 0; i < idx; i++) if (steps[i].status === "pending") steps[i] = { ...steps[i], status: "skipped" };
    }
    this._steps = steps;
    if (ev.step === "remove_entry" && ev.status === "done") refreshDevices(this);
  }

  private _event(ev: RevertEvent): void {
    switch (ev.type) {
      case "step":
        this._step(ev);
        break;
      case "done": {
        this._addLog({ kind: "info", text: "# Finished" });
        this._result = ev;
        this._steps = this._steps.map((s) => (s.status === "pending" ? { ...s, status: "skipped" } : s));
        if (this._steps.some((s) => s.status === "warning")) this._stepsOpen = true;
        this._stage = "done";
        this._stopSubscription();
        if (ev.entry_removed) refreshDevices(this);
        if (!this._open) {
          // the dialog was closed (e.g. the panel was left): report the result in a toast
          toast(this, ev.remaining.length ? `${this._name} was partly reverted` : `${this._name} was reverted to stock`, ev.remaining.length ? "warning" : "success");
        }
        break;
      }
      case "error":
        if (this._log.at(-1)?.text !== ev.error) this._addLog({ kind: "error", text: `Error: ${ev.error}` });
        this._failRunning(ev.error);
        this._error = ev.error;
        this._stage = "error";
        this._stopSubscription();
        break;
      default:
        break;
    }
  }

  // ------------------------------------------------------------------ log actions

  private async _copyLog(ev: Event): Promise<void> {
    ev.stopPropagation();
    await copyToClipboard(logText(this._log));
    toast(this, "Copied to clipboard");
  }

  private _downloadLog(ev: Event): void {
    ev.stopPropagation();
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    downloadText(`shelly-elevate-revert-${this._host || "display"}-${stamp}.txt`, `${logText(this._log)}\n`);
  }

  // ------------------------------------------------------------------ rendering

  private _title(): string {
    switch (this._stage) {
      case "host":
        return "Revert a display to stock";
      case "checking":
      case "confirm":
        return this._checkError ? "Could not check the display" : `Revert ${this._name} to stock?`;
      case "running":
        return `Reverting ${this._name}`;
      case "done":
        return this._result?.remaining.length ? "Partly reverted" : "Reverted to stock";
      default:
        return this._cancelled ? "Revert cancelled" : "Revert failed";
    }
  }

  private _subtitle(): string | undefined {
    if (this._stage === "host") return undefined;
    const name = this._name;
    if (this._stage === "done" || this._stage === "error") return name === this._host ? this._host : `${name} · ${this._host}`;
    return name !== this._host ? this._host : undefined;
  }

  private _renderHost() {
    const invalid = !!this._host && !HOST_RE.test(this._host);
    return html`
      <p class="dialog-text">
        Removes Shelly Elevate from a display and gives it back to the stock Shelly app. Home Assistant connects over ADB
        (port 5555) and first checks what is installed; nothing is changed until you confirm.
      </p>
      <ha-input
        label="IP address of the display"
        placeholder="192.168.1.50"
        inputmode="decimal"
        autocomplete="off"
        autofocus
        .value=${this._host}
        .invalid=${invalid}
        .validationMessage=${invalid ? "Enter an IP address or host name" : ""}
        @input=${(e: Event) => (this._host = inputValue(e).trim())}
        @keydown=${(e: KeyboardEvent) => e.key === "Enter" && this._runCheck()}
      ></ha-input>
    `;
  }

  /** As the progress step of HA's restore dialog: a centered spinner with the current state. */
  private _renderChecking() {
    return html`<div class="centered">
      <ha-spinner></ha-spinner>
      <p>Checking what is installed on ${this._host}…</p>
    </div>`;
  }

  private _optionsSchema(check: RevertCheckResult): HaFormSchema[] {
    const schema: HaFormSchema[] = [];
    if (check.entry_id) schema.push({ name: "remove_entry", selector: { boolean: {} } });
    if (check.check.wiki_launcher && check.check.stock_installed) {
      schema.push({ name: "remove_wiki_launcher", selector: { boolean: {} } });
    }
    schema.push({ name: "reboot", selector: { boolean: {} }, disabled: this._opts.disable_adb });
    schema.push({ name: "disable_adb", selector: { boolean: {} } });
    return schema;
  }

  private _renderConfirm() {
    if (this._checkError) {
      return html`<ha-alert alert-type="error">${this._checkError}</ha-alert>
        <p class="dialog-text secondary hint">
          ADB debugging and ADB over Wi‑Fi (port 5555) must be on in the Android developer options of the display;
          on newer Shelly firmware also ADB - WiFi in the Shelly developer settings.
        </p>`;
    }
    const check = this._check;
    if (!check) return nothing;
    const c = check.check;
    const platform = [
      check.platform.model,
      androidVersion(check.platform.sdk),
      check.platform.root ? "Rooted" : "Not rooted",
    ].filter(Boolean);
    const nothingInstalled = !c.app_installed && !c.priv_app && !c.init_rc && !c.legacy_v1;
    const data = { ...this._opts, reboot: this._opts.reboot && !this._opts.disable_adb };
    return html`
      <p class="dialog-text">
        ${nothingInstalled
          ? html`Shelly Elevate is not installed on this display. Reverting restores what an installation changed and gives the
              display back to the stock Shelly app.`
          : html`Home Assistant removes Shelly Elevate from ${this._name} over ADB and gives the display back to the stock
              Shelly app.`}
      </p>
      <p class="dialog-text secondary platform">${platform.join(" · ")}</p>
      ${check.warnings.map((code) => this._renderWarning(code))}
      <p class="dialog-text">This will:</p>
      <ul class="items">
        ${plannedChanges(check, this._opts).map((item) => html`<li>${item}</li>`)}
      </ul>
      <ha-form
        .hass=${this.api.hass}
        .data=${data}
        .schema=${this._optionsSchema(check)}
        .computeLabel=${(s: HaFormSchema) => OPTION_LABELS[s.name]?.[0] ?? s.name}
        .computeHelper=${(s: HaFormSchema) =>
          s.name === "reboot" && this._opts.disable_adb ? REBOOT_WITHOUT_ADB : OPTION_LABELS[s.name]?.[1]}
        @value-changed=${(e: ValueChangedEvent<Partial<RevertOptions>>) => {
          e.stopPropagation();
          const v = e.detail.value;
          this._opts = {
            ...this._opts,
            remove_entry: !!v.remove_entry,
            remove_wiki_launcher: !!v.remove_wiki_launcher,
            disable_adb: !!v.disable_adb,
            // keep the choice for when ADB stays on
            reboot: v.disable_adb ? this._opts.reboot : !!v.reboot,
          };
        }}
      ></ha-form>
    `;
  }

  private _renderWarning(code: string) {
    const w = WARNINGS[code];
    if (!w) return html`<ha-alert alert-type="warning">${code}</ha-alert>`;
    if (code !== "wifi_by_app") return html`<ha-alert alert-type=${w.type ?? "warning"} .title=${w.title}>${w.text}</ha-alert>`;
    return html`<ha-alert alert-type="error" .title=${w.title}>${w.text}</ha-alert>
      <ha-checkbox
        class="accept"
        .checked=${this._opts.accept_wifi_loss}
        @change=${(e: Event) => (this._opts = { ...this._opts, accept_wifi_loss: isChecked(e) })}
        >I understand that the display goes offline</ha-checkbox
      >`;
  }

  private _renderProgressBar() {
    const steps = this._steps;
    const finished = steps.filter((s) => FINISHED.has(s.status)).length;
    const running = steps.find((s) => s.status === "running");
    const value = this._stage === "done" ? 100 : steps.length ? Math.round((finished / steps.length) * 100) : 0;
    let status: string;
    if (this._stage === "done") {
      const warnings = steps.filter((s) => s.status === "warning").length;
      status = warnings ? `Finished – ${plural(warnings, "step")} did not work` : "Finished";
    } else if (this._stage === "error") {
      const failedAt = steps.findIndex((s) => s.status === "failed");
      const stopped = this._cancelled ? "Cancelled" : "Failed";
      status = failedAt >= 0 ? `${stopped} at step ${failedAt + 1} of ${steps.length}: ${steps[failedAt].label}` : stopped;
    } else {
      status = `Step ${Math.min(finished + 1, steps.length)} of ${steps.length}: ${running?.label ?? "Starting…"}`;
    }
    return html`
      ${this._hasProgressBar
        ? html`<ha-progress-bar .value=${value} ?loading=${this._stage === "running"} aria-label="Revert progress"></ha-progress-bar>`
        : html`<progress max="100" .value=${value}></progress>`}
      <p class="status" role="status">${status}</p>
    `;
  }

  private _renderResult() {
    const result = this._result;
    if (this._stage === "error") {
      return this._cancelled
        ? html`<ha-alert alert-type="warning" title="Revert cancelled">
            The display may be partly reverted. You can run the revert again.
          </ha-alert>`
        : html`<ha-alert alert-type="error" title="Revert failed">${this._error}</ha-alert>`;
    }
    if (this._stage === "running") {
      return html`<ha-alert alert-type="info">Keep this page open until the revert has finished.</ha-alert>`;
    }
    if (!result) return nothing;
    const after: string[] = [];
    if (result.entry_removed) after.push(`${this._name} was removed from Home Assistant.`);
    if (result.adb_disabled) after.push("ADB over Wi‑Fi is turned off. Restart the display to finish.");
    else if (this._steps.find((s) => s.id === "reboot")?.status === "done") after.push("The display is restarting.");
    if (!result.remaining.length) {
      return html`<ha-alert alert-type="success" title="The stock Shelly app is back">
        ${this._check && !this._check.check.app_installed && !this._check.check.priv_app
          ? "Shelly Elevate was not installed; what an installation changes was reset."
          : "Shelly Elevate was removed from the display."}
        ${after.join(" ")}
      </ha-alert>`;
    }
    return html`<ha-alert alert-type="warning" title="Not everything could be reverted">
      <ul class="remaining">
        ${result.remaining.map((r) => html`<li>${REMAINING[r] ?? r}</li>`)}
      </ul>
      ${after.join(" ")}
    </ha-alert>`;
  }

  private _renderProgress() {
    const finished = this._steps.filter((s) => FINISHED.has(s.status) && s.status !== "failed").length;
    return html`
      ${this._renderProgressBar()} ${this._renderResult()}
      <div class="panels">
        <ha-expansion-panel
          outlined
          .header=${"Steps"}
          .secondary=${`${finished} of ${this._steps.length} done`}
          .expanded=${this._stepsOpen}
          @expanded-changed=${(e: CustomEvent<{ expanded: boolean }>) => {
            e.stopPropagation();
            this._stepsOpen = e.detail.expanded;
          }}
        >
          <sep-step-list .steps=${this._steps}></sep-step-list>
        </ha-expansion-panel>
        <ha-expansion-panel
          class="log"
          outlined
          .header=${"Log"}
          .secondary=${`${this._log.length} ${this._log.length === 1 ? "line" : "lines"}`}
          .expanded=${this._logOpen}
          @expanded-changed=${(e: CustomEvent<{ expanded: boolean }>) => {
            e.stopPropagation();
            this._logOpen = e.detail.expanded;
          }}
        >
          <ha-icon-button
            slot="icons"
            .label=${"Copy to clipboard"}
            .path=${mdiContentCopy}
            ?disabled=${!this._log.length}
            @click=${this._copyLog}
            @keydown=${stopPropagation}
          ></ha-icon-button>
          <ha-icon-button
            slot="icons"
            .label=${"Download log"}
            .path=${mdiDownload}
            ?disabled=${!this._log.length}
            @click=${this._downloadLog}
            @keydown=${stopPropagation}
          ></ha-icon-button>
          <sep-install-log .lines=${this._log}></sep-install-log>
        </ha-expansion-panel>
      </div>
    `;
  }

  private _renderBody() {
    switch (this._stage) {
      case "host":
        return this._renderHost();
      case "checking":
        return this._renderChecking();
      case "confirm":
        return this._renderConfirm();
      default:
        return this._renderProgress();
    }
  }

  private _renderFooter() {
    const cancel = html`<ha-button slot="secondaryAction" appearance="plain" @click=${this._close}>Cancel</ha-button>`;
    switch (this._stage) {
      case "host":
        return html`${cancel}
          <ha-button slot="primaryAction" ?disabled=${!HOST_RE.test(this._host)} @click=${this._runCheck}>Check display</ha-button>`;
      case "checking":
        return cancel;
      case "confirm": {
        if (this._checkError || !this._check) {
          return html`<ha-button
              slot="secondaryAction"
              appearance="plain"
              @click=${() => (this._target.host ? this._close() : (this._stage = "host"))}
              >${this._target.host ? "Close" : "Back"}</ha-button
            >
            <ha-button slot="primaryAction" @click=${this._runCheck}>Try again</ha-button>`;
        }
        const blocked = this._check.warnings.includes("wifi_by_app") && !this._opts.accept_wifi_loss;
        return html`${cancel}
          <ha-button slot="primaryAction" variant="danger" ?disabled=${blocked} @click=${this._start}>Revert to stock</ha-button>`;
      }
      case "running":
        return html`<ha-button slot="secondaryAction" appearance="plain" variant="danger" @click=${this._askCancel}
          >Cancel</ha-button
        >`;
      case "done":
        return html`<ha-button slot="primaryAction" @click=${this._close}>Close</ha-button>`;
      default:
        return html`<ha-button slot="secondaryAction" appearance="plain" @click=${this._close}>Close</ha-button>
          <ha-button slot="primaryAction" @click=${this._runCheck}>Try again</ha-button>`;
    }
  }

  render() {
    const running = this._stage === "running";
    return html`
      <ha-dialog
        .open=${this._open}
        .headerTitle=${this._title()}
        .headerSubtitle=${this._subtitle()}
        .preventScrimClose=${this._stage !== "host" && this._stage !== "checking"}
        @closed=${this._closed}
      >
        ${running ? html`<span slot="headerNavigationIcon"></span>` : nothing}
        <div class="revert">${this._renderBody()}</div>
        <ha-dialog-footer slot="footer">${this._renderFooter()}</ha-dialog-footer>
      </ha-dialog>
    `;
  }

  static styles = [
    sharedStyles,
    dialogStyles,
    css`
      /* dialog-restore-backup */
      .centered {
        display: flex;
        flex-direction: column;
        align-items: center;
      }
      .centered ha-spinner {
        margin-bottom: var(--ha-space-4);
      }
      .centered p {
        margin: 0;
        color: var(--primary-text-color);
      }
      .platform,
      .hint {
        margin-top: calc(var(--ha-space-2) * -1);
      }
      ha-alert {
        margin-bottom: var(--ha-space-4);
      }
      ha-checkbox.accept {
        display: block;
        margin: calc(var(--ha-space-2) * -1) 0 var(--ha-space-4);
      }
      /* the bullet list of dialog-box (see the panel's confirm dialog) */
      .items {
        margin: calc(var(--ha-space-2) * -1) 0 var(--ha-space-4);
        padding-inline-start: var(--ha-space-5);
        color: var(--primary-text-color);
      }
      .items li {
        margin-bottom: var(--ha-space-1);
      }
      .remaining {
        margin: 0 0 var(--ha-space-1);
        padding-inline-start: var(--ha-space-5);
      }
      ha-form {
        display: block;
      }
      ha-progress-bar,
      progress {
        display: block;
        width: 100%;
      }
      p.status {
        margin: var(--ha-space-2) 0 var(--ha-space-4);
        color: var(--secondary-text-color);
      }
      .panels {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-2);
      }
      sep-step-list {
        --ha-row-item-padding-inline: 0;
      }
      ha-expansion-panel.log {
        --expansion-panel-content-padding: 0;
      }
      sep-install-log {
        line-height: var(--ha-line-height-normal);
      }
      ha-expansion-panel ha-icon-button {
        color: var(--secondary-text-color);
        margin: -8px 0;
      }
    `,
  ];
}

define("sep-revert-dialog", SeRevertDialog);

declare global {
  interface HTMLElementTagNameMap {
    "sep-revert-dialog": SeRevertDialog;
  }
}
