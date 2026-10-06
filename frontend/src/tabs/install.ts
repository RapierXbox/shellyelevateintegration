import { LitElement, type PropertyValues, css, html, nothing } from "lit";
import { mdiContentCopy, mdiDownload } from "@mdi/js";
import {
  type DeviceSummary,
  ElevateApi,
  type InstallerDoneEvent,
  type InstallerEvent,
  type InstallerInfo,
  type ProvisionOptions,
  type StepEvent,
  errorMessage,
} from "../api";
import {
  type HaFormSchema,
  type UnsubscribeFunc,
  type ValueChangedEvent,
  copyToClipboard,
  inputValue,
  isDefined,
  loadProgressBar,
  navigate,
} from "../ha";
import { type PageContext, pageStyles, renderPage } from "../page";
import { sharedStyles } from "../styles";
import {
  androidVersion,
  confirmDialog,
  define,
  downloadText,
  openRevert,
  openTab,
  plural,
  refreshDevices,
  stopPropagation,
  toast,
} from "../ui";
import type { StepState } from "../components/step-list";
import "../components/step-list";
import { type LogLine, commandLine, logText } from "../components/install-log";
import "../components/install-log";

// --------------------------------------------------------------------------- static data

const PROVISION_LABELS: Record<string, string> = {
  adb_connect: "Connect over ADB",
  root_check: "Check for root",
  dev_settings: "Enable developer settings",
  adb_enabled: "Enable ADB debugging",
  adb_wifi: "Enable ADB over Wi‑Fi",
  adb_tcp: "Keep ADB on port 5555 after reboot",
  adb_key: "Trust Home Assistant's ADB key",
  download: "Download the Shelly Elevate app",
  push: "Copy the app to the display",
  install: "Install the app",
  cleanup: "Clean up",
  perm_audio: "Grant microphone permission",
  perm_location: "Grant location permission",
  perm_bt_scan: "Grant Bluetooth scan permission",
  perm_bt_connect: "Grant Bluetooth connect permission",
  write_settings: "Allow changing system settings",
  overlay: "Allow drawing over other apps",
  doze_whitelist: "Exclude from battery optimisation",
  disable_stock: "Keep the stock Shelly app in the background",
  stop: "Stop the app",
  start: "Start the app",
  wait_app: "Wait for the app to start",
  provision: "Pair with Home Assistant",
  config_entry: "Add the display to Home Assistant",
};

/** ADB post-install steps whose failure does not stop the installation. */
const NON_FATAL = new Set([
  "root_check",
  "dev_settings",
  "adb_enabled",
  "adb_wifi",
  "adb_tcp",
  "adb_key",
  "perm_audio",
  "perm_location",
  "perm_bt_scan",
  "perm_bt_connect",
  "write_settings",
  "overlay",
  "doze_whitelist",
  "disable_stock",
  "stop",
  "start",
]);

/** Steps that only run from Android 12 (API 31) on. */
const ANDROID_12_STEPS = new Set(["perm_bt_scan", "perm_bt_connect"]);
const ANDROID_12 = 31;

/** Final steps; steps the initial list does not know are inserted before them. */
const FINAL_STEPS = ["wait_app", "provision", "config_entry"];

const TAP_SEQUENCE = ["F", "H", "F", "F", "H", "F", "H", "H"];

/** Step 1 instructions (the user-confirmed ADB steps), as config flow descriptions are written. */
const ADB_STEPS_MARKDOWN = `ADB has to be enabled once on the display. Home Assistant then installs and sets up everything over the network.

1. Connect the display to Wi‑Fi in the Shelly settings under **Network**.
2. Update the display to the newest Shelly firmware.
3. In the Shelly settings, open **General → About device** and tap **Firmware** (F) and **Hardware** (H) in this order: **${TAP_SEQUENCE.join(" ")}**
4. In the Android **Developer options**, enable only **ADB debugging** and **ADB over Wi‑Fi** (port 5555). On newer Shelly firmware, also turn on **ADB - WiFi** in the Shelly developer settings (it shows the display's address with port 5555). Note the IP address of the display.
5. Enter the IP address below.`;

/** Step states that count as finished for the progress bar. */
const FINISHED = new Set<StepState["status"]>(["done", "failed", "warning", "skipped"]);

/** ha-form select value for "no profile" (null is not a valid option value). */
const NO_PROFILE = "__none__";

type Stage = "adb" | "provision";
type RunState = "idle" | "running" | "done" | "error";

const HOST_RE = /^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?!$)|$)){4}$|^[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?$/;

const provisionStepsFor = (opts: ProvisionOptions): StepState[] => {
  const ids = ["adb_connect", "root_check", "dev_settings", "adb_enabled", "adb_wifi", "adb_tcp"];
  if (opts.install_app) ids.push("download", "push", "install", "cleanup");
  ids.push("perm_audio", "perm_location", "perm_bt_scan", "perm_bt_connect", "write_settings", "overlay", "doze_whitelist");
  if (opts.disable_stock) ids.push("disable_stock");
  ids.push("start", ...FINAL_STEPS);
  return ids.map((id) => ({ id, label: PROVISION_LABELS[id] ?? id, status: "pending" }));
};

const formatBytes = (n: number): string =>
  n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.round(n / 1024)} kB`;

/** Detail text of a step event (undefined: keep the current detail). */
const stepDetail = (ev: StepEvent, current?: string): string | undefined => {
  if (ev.error) return String(ev.error);
  switch (`${ev.step}:${ev.status}`) {
    case "root_check:done": {
      const parts = [ev.root === false ? "Not rooted" : ev.root === true ? "Rooted" : "", androidVersion(ev.sdk)];
      return parts.filter(Boolean).join(" · ") || current;
    }
    case "download:running":
      return ev.version ? `Version ${ev.version}` : current;
    case "download:done":
      return ev.bytes ? `${current ? `${current} · ` : ""}${formatBytes(ev.bytes)}` : current;
    case "push:running":
      return ev.bytes ? formatBytes(ev.bytes) : current;
    case "wait_app:done":
      return `${ev.legacy ? "Legacy app" : "App"}${ev.version ? ` ${ev.version}` : ""} is running`;
    case "config_entry:done":
      return ev.updated ? "Already configured – existing entry updated" : current;
    default:
      return current;
  }
};

const OPTION_LABELS: Record<string, [string, string?]> = {
  install_app: ["Install the Shelly Elevate app", "Downloads the version chosen below from GitHub and installs it."],
  release: [
    "App version",
    "Latest installs the newest release of the channel. Pick a version to install exactly that one.",
  ],
  disable_stock: [
    "Keep the stock Shelly app in the background",
    "Keeps the stock Shelly app from covering Shelly Elevate. On Android 11 models (Wall Display XL, X2i, X1i) the stock app is only kept from drawing on top and stopped; on older models it is disabled, which leaves the display without a home app.",
  ],
  profile_id: ["Settings profile", "Applied to the display after pairing."],
  dashboard_url: ["Dashboard URL", "The page the display shows, e.g. http://homeassistant.local:8123/lovelace/0"],
};

/** Form data of the options form (ha-form needs plain values). */
interface OptionsForm extends Omit<ProvisionOptions, "profile_id" | "dashboard_url" | "channel" | "version"> {
  /** "stable", "beta" (latest of that channel) or "v:<version>" */
  release: string;
  profile_id: string;
  dashboard_url: string;
}

const VERSION_PREFIX = "v:";

// --------------------------------------------------------------------------- element

/** Install wizard: prepare the display (ADB), then install + pair it over ADB with live progress. */
export class SeInstallTab extends LitElement {
  static properties = {
    page: { attribute: false },
    api: { attribute: false },
    devices: { attribute: false },
    active: { type: Boolean },
    narrow: { type: Boolean, reflect: true },
    _info: { state: true },
    _infoError: { state: true },
    _stage: { state: true },
    _host: { state: true },
    _opts: { state: true },
    _provState: { state: true },
    _provSteps: { state: true },
    _provError: { state: true },
    _provResult: { state: true },
    _log: { state: true },
    _logOpen: { state: true },
    _stepsOpen: { state: true },
    _hasProgressBar: { state: true },
  };

  declare page: PageContext;
  declare api: ElevateApi;
  declare devices: DeviceSummary[];
  /** The tab is shown (the element stays mounted while other tabs are open). */
  declare active: boolean;
  declare narrow: boolean;
  declare _info: InstallerInfo | null;
  declare _infoError: string;
  declare _stage: Stage;
  declare _host: string;
  declare _opts: ProvisionOptions;
  declare _provState: RunState;
  declare _provSteps: StepState[];
  declare _provError: string;
  declare _provResult: InstallerDoneEvent | null;
  /** Commands and their output of the current run. */
  declare _log: LogLine[];
  declare _logOpen: boolean;
  declare _stepsOpen: boolean;
  declare _hasProgressBar: boolean;

  private _unsub: UnsubscribeFunc | null = null;
  /** The run was cancelled by the user. */
  private _cancelled = false;
  /** config_entry: the display was already set up; its entry was updated. */
  private _updated = false;

  constructor() {
    super();
    this.devices = [];
    this.active = false;
    this.narrow = false;
    this._info = null;
    this._infoError = "";
    this._stage = "adb";
    this._host = "";
    this._opts = {
      install_app: true,
      channel: "stable",
      version: null,
      disable_stock: false,
      profile_id: null,
      dashboard_url: null,
    };
    this._provState = "idle";
    this._provSteps = [];
    this._provError = "";
    this._provResult = null;
    this._log = [];
    this._logOpen = false;
    this._stepsOpen = false;
    this._hasProgressBar = isDefined("ha-progress-bar");
  }

  // ------------------------------------------------------------------ lifecycle

  protected willUpdate(changed: PropertyValues<this>): void {
    if (changed.has("active") && this.active && this.api && !this._busy) this._loadInfo();
    if (changed.has("page") && this.page && !this._hasProgressBar) {
      loadProgressBar(this.page.hass, this.renderRoot).then((ok) => (this._hasProgressBar = ok));
    }
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._stopSubscription();
  }

  private get _busy(): boolean {
    return this._provState === "running";
  }

  private get _hostValid(): boolean {
    return HOST_RE.test(this._host);
  }

  private async _loadInfo(): Promise<void> {
    const first = this._info === null;
    try {
      const info = await this.api.installerInfo();
      this._info = info;
      this._infoError = "";
      if (first) {
        this._opts = {
          ...this._opts,
          profile_id: info.default_profile ?? null,
          dashboard_url: info.dashboard_url ?? null,
        };
      } else if (this._opts.profile_id && !info.profiles.some((p) => p.id === this._opts.profile_id)) {
        this._opts = { ...this._opts, profile_id: info.default_profile ?? null };
      }
    } catch (err) {
      this._infoError = errorMessage(err);
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

  // ------------------------------------------------------------------ navigation

  private _back(): void {
    this._stage = "adb";
    this._resetProvision();
  }

  private async _askCancel(): Promise<void> {
    const ok = await confirmDialog(this, {
      title: "Cancel the installation?",
      text: "The running step is stopped. The display may be left half-configured; you can run the installation again.",
      confirmText: "Cancel installation",
      dismissText: "Keep installing",
      destructive: true,
    });
    if (ok && this._busy) await this._cancel();
  }

  private async _cancel(): Promise<void> {
    await this._stopSubscription();
    if (this._provState === "running") {
      this._addLog({ kind: "error", text: "Cancelled" });
      this._provState = "error";
      this._provError = "";
      this._cancelled = true;
    }
    this._failRunning("Cancelled");
  }

  private _resetProvision(): void {
    this._cancelled = false;
    this._updated = false;
    this._provState = "idle";
    this._provSteps = [];
    this._provError = "";
    this._provResult = null;
    this._log = [];
    this._stepsOpen = false;
  }

  private _restart(): void {
    this._stage = "adb";
    this._host = "";
    this._resetProvision();
    this._loadInfo();
  }

  /** "Revert to stock": asks for the address (the one entered here, if any). */
  private _revert(): void {
    openRevert(this, { prefill: this._hostValid ? this._host.trim() : "" });
  }

  /** Revert the display the installation failed on (e.g. an old app signed with another key). */
  private _revertHost(): void {
    openRevert(this, { host: this._host.trim() });
  }

  private _continue(): void {
    if (this._hostValid) this._stage = "provision";
  }

  // ------------------------------------------------------------------ step bookkeeping

  /** Mark the running step as failed (keeping a detail it already has). */
  private _failRunning(detail: string): void {
    if (!this._provSteps.some((s) => s.status === "running")) return;
    this._provSteps = this._provSteps.map((s) =>
      s.status === "running" ? { ...s, status: "failed", detail: s.detail || detail } : s,
    );
  }

  /** Index of the step `id`; steps not in the initial list are inserted first. */
  private _stepIndex(steps: StepState[], id: string): number {
    const idx = steps.findIndex((s) => s.id === id);
    if (idx >= 0) return idx;
    // adb_key only runs on rooted displays and goes right after adb_tcp; unknown steps go
    // before the final HA steps if possible.
    const after = id === "adb_key" ? steps.findIndex((s) => s.id === "adb_tcp") : -1;
    const at = after >= 0 ? after + 1 : steps.findIndex((s) => s.id === FINAL_STEPS[0]);
    const step: StepState = { id, label: PROVISION_LABELS[id] ?? id, status: "pending" };
    if (at >= 0 && !FINAL_STEPS.includes(id)) {
      steps.splice(at, 0, step);
      return at;
    }
    steps.push(step);
    return steps.length - 1;
  }

  private _addLog(...lines: LogLine[]): void {
    this._log = [...this._log, ...lines];
  }

  /** Log lines of a step event: "$ command", its output, errors. */
  private _logStep(ev: StepEvent, label: string): void {
    if (ev.status === "running") {
      this._addLog(ev.command ? commandLine(ev.command) : { kind: "info", text: `# ${label}` });
    } else if (ev.status === "failed") {
      this._addLog({ kind: NON_FATAL.has(ev.step) ? "warning" : "error", text: String(ev.error ?? "failed") });
    } else if (ev.status === "done") {
      const out = ev.output?.replace(/\r/g, "").trimEnd();
      if (out) this._addLog(...out.split("\n").map((text): LogLine => ({ kind: "output", text })));
      else if (ev.step === "download" && ev.bytes) this._addLog({ kind: "output", text: `${ev.bytes} bytes` });
    }
  }

  private _provisionStep(ev: StepEvent): void {
    if (ev.step === "config_entry" && ev.status === "done") this._updated = !!ev.updated;
    let steps = [...this._provSteps];
    // The Bluetooth permissions only exist from Android 12 on; older displays never run them.
    if (ev.step === "root_check" && ev.status === "done" && "sdk" in ev && !((ev.sdk ?? 0) >= ANDROID_12)) {
      steps = steps.filter((s) => !ANDROID_12_STEPS.has(s.id));
    }
    const idx = this._stepIndex(steps, ev.step);
    const step = steps[idx];
    this._logStep(ev, step.label);
    steps[idx] = {
      ...step,
      status: ev.status === "failed" && NON_FATAL.has(ev.step) ? "warning" : ev.status,
      detail: stepDetail(ev, step.detail),
    };
    // Steps before the current one that never reported were skipped by the backend.
    if (ev.status === "running") {
      for (let i = 0; i < idx; i++) if (steps[i].status === "pending") steps[i] = { ...steps[i], status: "skipped" };
    }
    this._provSteps = steps;
  }

  private _provisionEvent(ev: InstallerEvent): void {
    switch (ev.type) {
      case "step":
        this._provisionStep(ev);
        break;
      case "done":
        this._addLog({ kind: "info", text: "# Finished" });
        this._provState = "done";
        this._provResult = ev;
        this._provSteps = this._provSteps.map((s) => (s.status === "pending" ? { ...s, status: "skipped" } : s));
        // Show the steps when some of them did not work.
        if (this._provSteps.some((s) => s.status === "warning")) this._stepsOpen = true;
        this._stopSubscription();
        refreshDevices(this);
        toast(this, `${ev.name ?? "The display"} was ${this._updated ? "updated" : "added to Home Assistant"}`, "success");
        break;
      case "error":
        // the failed step usually logged the same message already
        if (this._log.at(-1)?.text !== ev.error) this._addLog({ kind: "error", text: `Error: ${ev.error}` });
        this._provState = "error";
        this._provError = ev.error;
        // The alert names the failed step; the step list stays as it is, so the actions stay in view.
        this._failRunning(ev.error);
        this._stopSubscription();
        break;
      default:
        break;
    }
  }

  // ------------------------------------------------------------------ provisioning

  private async _startProvision(): Promise<void> {
    const host = this._host.trim();
    if (!HOST_RE.test(host)) {
      toast(this, "Enter the display's IP address", "warning");
      return;
    }
    this._resetProvision();
    this._provState = "running";
    this._provSteps = provisionStepsFor(this._opts);
    try {
      this._unsub = await this.api.subscribeProvision(host, this._opts, (ev) => this._provisionEvent(ev));
    } catch (err) {
      this._provState = "error";
      this._provError = errorMessage(err);
    }
  }

  // ------------------------------------------------------------------ log actions

  private _logFileName(): string {
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    return `shelly-elevate-install-${this._host || "display"}-${stamp}.txt`;
  }

  private async _copyLog(ev: Event): Promise<void> {
    ev.stopPropagation();
    await copyToClipboard(logText(this._log));
    toast(this, "Copied to clipboard");
  }

  private _downloadLog(ev: Event): void {
    ev.stopPropagation();
    downloadText(this._logFileName(), `${logText(this._log)}\n`);
  }

  // ------------------------------------------------------------------ rendering

  private _hostInput(disabled: boolean, onEnter?: () => void) {
    const invalid = !!this._host && !this._hostValid;
    return html`<ha-input
      label="IP address of the display"
      placeholder="192.168.1.50"
      inputmode="decimal"
      autocomplete="off"
      .value=${this._host}
      .invalid=${invalid}
      .validationMessage=${invalid ? "Enter an IP address or host name" : ""}
      ?disabled=${disabled}
      @input=${(e: Event) => (this._host = inputValue(e).trim())}
      @keydown=${(e: KeyboardEvent) => e.key === "Enter" && onEnter?.()}
    ></ha-input>`;
  }

  /** Description of a step, rendered by ha-markdown like the description of a config flow step. */
  private _renderDescription(markdown: string) {
    return isDefined("ha-markdown") ? html`<ha-markdown .content=${markdown}></ha-markdown>` : html`<p>${markdown}</p>`;
  }

  /** Instructions of step 1: rendered by ha-markdown like the description of a config flow step. */
  private _renderAdbSteps() {
    if (isDefined("ha-markdown")) return this._renderDescription(ADB_STEPS_MARKDOWN);
    return html`
      <p>ADB has to be enabled once on the display. Home Assistant then installs and sets up everything over the network.</p>
      <ol>
        <li>Connect the display to Wi‑Fi in the Shelly settings under <b>Network</b>.</li>
        <li>Update the display to the newest Shelly firmware.</li>
        <li>
          In the Shelly settings, open <b>General → About device</b> and tap <b>Firmware</b> (F) and
          <b>Hardware</b> (H) in this order: <b>${TAP_SEQUENCE.join(" ")}</b>
        </li>
        <li>
          In the Android <b>Developer options</b>, enable only <b>ADB debugging</b> and <b>ADB over Wi‑Fi</b> (port
          5555). On newer Shelly firmware, also turn on <b>ADB - WiFi</b> in the Shelly developer settings (it shows
          the display's address with port 5555). Note the IP address of the display.
        </li>
        <li>Enter the IP address below.</li>
      </ol>
    `;
  }

  private _renderAdbStage() {
    return html`
      <ha-card>
        <h1 class="card-header">Prepare the display</h1>
        <div class="card-content">
          ${this._renderAdbSteps()} ${this._hostInput(false, () => this._continue())}
        </div>
        <div class="card-actions">
          <ha-button appearance="filled" ?disabled=${!this._hostValid} @click=${this._continue}>Next</ha-button>
        </div>
      </ha-card>
      <ha-card>
        <h1 class="card-header">Revert a display to stock</h1>
        <div class="card-content">
          <p>
            Removes Shelly Elevate and everything its installation changed, and gives the display back to the stock Shelly
            app. Also works for displays that are not in Home Assistant.
          </p>
        </div>
        <div class="card-actions">
          <ha-button appearance="plain" @click=${this._revert}>Revert a display…</ha-button>
        </div>
      </ha-card>
    `;
  }

  private _optionsSchema(): HaFormSchema[] {
    const releases = this._info?.releases ?? [];
    const latestLabel = (beta: boolean) => {
      const latest = releases.find((r) => beta || !r.prerelease)?.version;
      return `Latest ${beta ? "beta" : "stable"}${latest ? ` (${latest})` : ""}`;
    };
    const release: HaFormSchema = {
      name: "release",
      required: true,
      selector: {
        select: {
          mode: "dropdown",
          options: [
            { value: "stable", label: latestLabel(false) },
            { value: "beta", label: latestLabel(true) },
            ...releases.map((r) => ({
              value: `${VERSION_PREFIX}${r.version}`,
              label: [
                r.version,
                r.prerelease ? "beta" : "",
                r.published ? new Date(r.published).toLocaleDateString(this.page.hass.locale?.language) : "",
              ]
                .filter(Boolean)
                .join(" · "),
            })),
          ],
        },
      },
    };
    return [
      { name: "install_app", selector: { boolean: {} } },
      ...(this._opts.install_app ? [release] : []),
      { name: "disable_stock", selector: { boolean: {} } },
      {
        name: "profile_id",
        required: true,
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: NO_PROFILE, label: "No profile" },
              ...(this._info?.profiles ?? []).map((p) => ({ value: p.id, label: `${p.name}${p.default ? " (default)" : ""}` })),
            ],
          },
        },
      },
      { name: "dashboard_url", selector: { text: { type: "url" } } },
    ];
  }

  private _renderOptions(disabled: boolean) {
    const { channel, version, ...rest } = this._opts;
    const data: OptionsForm = {
      ...rest,
      release: version ? `${VERSION_PREFIX}${version}` : channel,
      profile_id: this._opts.profile_id || NO_PROFILE,
      dashboard_url: this._opts.dashboard_url ?? "",
    };
    return html`<ha-form
      .hass=${this.page.hass}
      .data=${data}
      .schema=${this._optionsSchema()}
      .disabled=${disabled}
      .computeLabel=${(s: HaFormSchema) => OPTION_LABELS[s.name]?.[0] ?? s.name}
      .computeHelper=${(s: HaFormSchema) => OPTION_LABELS[s.name]?.[1]}
      @value-changed=${(e: ValueChangedEvent<Partial<OptionsForm>>) => {
        e.stopPropagation();
        const v = e.detail.value;
        const picked = v.release ?? "stable";
        this._opts = {
          install_app: !!v.install_app,
          channel: picked === "beta" ? "beta" : "stable",
          version: picked.startsWith(VERSION_PREFIX) ? picked.slice(VERSION_PREFIX.length) : null,
          disable_stock: !!v.disable_stock,
          profile_id: v.profile_id && v.profile_id !== NO_PROFILE ? v.profile_id : null,
          dashboard_url: v.dashboard_url || null,
        };
      }}
    ></ha-form>`;
  }

  /** Overall progress: HA's progress bar (as in the update dialog) and the current step. */
  private _renderProgressBar() {
    const steps = this._provSteps;
    const finished = steps.filter((s) => FINISHED.has(s.status)).length;
    const running = steps.find((s) => s.status === "running");
    const state = this._provState;
    const value = state === "done" ? 100 : steps.length ? Math.round((finished / steps.length) * 100) : 0;
    const failedAt = steps.findIndex((s) => s.status === "failed");
    const warnings = steps.filter((s) => s.status === "warning").length;
    const stopped = this._cancelled ? "Cancelled" : "Failed";
    let status: string;
    if (state === "done") {
      status = warnings ? `Finished – ${plural(warnings, "optional step")} did not work` : "Finished";
    } else if (state === "error") {
      status = failedAt >= 0 ? `${stopped} at step ${failedAt + 1} of ${steps.length}: ${steps[failedAt].label}` : stopped;
    } else {
      status = `Step ${Math.min(finished + 1, steps.length)} of ${steps.length}: ${running?.label ?? "Starting…"}`;
    }
    return html`
      ${this._hasProgressBar
        ? html`<ha-progress-bar .value=${value} ?loading=${state === "running"} aria-label="Installation progress"></ha-progress-bar>`
        : html`<progress max="100" .value=${value}></progress>`}
      <p class="status" role="status">${status}</p>
    `;
  }

  private _renderProgress() {
    const result = this._provResult;
    const state = this._provState;
    const finished = this._provSteps.filter((s) => FINISHED.has(s.status) && s.status !== "failed").length;
    return html`
      <ha-card>
        <h1 class="card-header">Installation on ${this._host}</h1>
        <div class="card-content">
          ${this._renderProgressBar()}
          ${state === "error" && this._cancelled
            ? html`<ha-alert alert-type="warning" title="Installation cancelled">
                The display may be partly set up. You can run the installation again.
              </ha-alert>`
            : nothing}
          ${state === "error" && !this._cancelled
            ? html`<ha-alert alert-type="error" title="Installation failed">
                ${this._provError}
                ${/revert the display/i.test(this._provError)
                  ? html`<ha-button slot="action" appearance="plain" @click=${this._revertHost}>Revert…</ha-button>`
                  : nothing}
              </ha-alert>`
            : nothing}
          ${state === "done" && result ? this._renderSuccess(result) : nothing}
          ${state === "running"
            ? html`<ha-alert alert-type="info">Keep this page open until the installation has finished.</ha-alert>`
            : nothing}
          <div class="panels">
            <ha-expansion-panel
              outlined
              .header=${"Steps"}
              .secondary=${`${finished} of ${this._provSteps.length} done`}
              .expanded=${this._stepsOpen}
              @expanded-changed=${(e: CustomEvent<{ expanded: boolean }>) => {
                e.stopPropagation();
                this._stepsOpen = e.detail.expanded;
              }}
            >
              <sep-step-list .steps=${this._provSteps}></sep-step-list>
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
        </div>
        ${state === "done"
          ? html`<div class="card-actions">
              <ha-button appearance="plain" @click=${this._restart}>Install another display</ha-button>
              ${this._renderOpenDevice(result)}
            </div>`
          : state === "running"
            ? html`<div class="card-actions">
                <ha-button appearance="plain" variant="danger" @click=${this._askCancel}>Cancel</ha-button>
              </div>`
            : html`<div class="card-actions split">
                <ha-button appearance="plain" @click=${this._resetProvision}>Back</ha-button>
                <ha-button appearance="filled" @click=${this._startProvision}>Try again</ha-button>
              </div>`}
      </ha-card>
    `;
  }

  /** Result of a finished run: a new display, or one that was already set up and got updated. */
  private _renderSuccess(result: InstallerDoneEvent) {
    const name = result.name ?? "The display";
    const warnings = this._provSteps.some((s) => s.status === "warning");
    const text = this._updated
      ? `${name} was already set up in Home Assistant. Its address and pairing were updated.`
      : result.legacy
        ? `${name} runs the legacy app and was added to Home Assistant.`
        : "Shelly Elevate is installed and paired with Home Assistant.";
    return html`<ha-alert alert-type="success" title="${name} is ready">
      ${text}${warnings ? " Some optional steps did not work; they are marked under Steps." : ""}
    </ha-alert>`;
  }

  /** Main action after a run: the display's device page (Show displays until it is listed). */
  private _renderOpenDevice(result: InstallerDoneEvent | null) {
    const deviceId =
      result?.device_id ??
      (result?.entry_id ? this.devices.find((d) => d.entry_id === result.entry_id)?.device_id : undefined);
    if (deviceId) {
      const path = `/config/devices/device/${deviceId}`;
      return html`<ha-button appearance="filled" @click=${() => navigate(path)}>Open device</ha-button>`;
    }
    return html`<ha-button appearance="filled" @click=${() => openTab(this, "displays")}>Show displays</ha-button>`;
  }

  /** Options of the installation; replaced by the progress card once it runs (like a config flow step). */
  private _renderProvisionStage() {
    if (this._provState !== "idle") return this._renderProgress();
    return html`
      <ha-card>
        <h1 class="card-header">Install and pair</h1>
        <div class="card-content">
          ${this._renderDescription("Home Assistant connects to the display over ADB, installs the app and adds the display.")}
          ${this._hostInput(false, () => this._startProvision())} ${this._renderOptions(false)}
        </div>
        <div class="card-actions split">
          <ha-button appearance="plain" @click=${this._back}>Back</ha-button>
          <ha-button appearance="filled" ?disabled=${!this._hostValid} @click=${this._startProvision}>Install</ha-button>
        </div>
      </ha-card>
    `;
  }

  private _renderBody() {
    if (this._infoError && !this._info) {
      return html`<ha-alert alert-type="error" title="Could not load the installer">
        ${this._infoError}
        <ha-button slot="action" appearance="plain" @click=${this._loadInfo}>Retry</ha-button>
      </ha-alert>`;
    }
    if (!this._info) return html`<div class="loading"><ha-spinner></ha-spinner></div>`;
    return this._stage === "provision" ? this._renderProvisionStage() : this._renderAdbStage();
  }

  render() {
    if (!this.page) return nothing;
    return renderPage(this, this.page, html`<div class="content">${this._renderBody()}</div>`);
  }

  static styles = [
    sharedStyles,
    pageStyles,
    css`
      /* text / form cards: ha-card's own header spacing (as System → General); the 8px variant of
         sharedStyles is for cards that continue with list rows */
      .card-header {
        padding-bottom: var(--ha-space-6);
      }
      .card-content > p:first-child {
        margin-top: 0;
      }
      /* fallback list without ha-markdown: same metrics as ha-markdown's */
      ol {
        margin: 1em 0 0;
      }
      /* description → first field: 24px as in a config flow step (step-flow-form) */
      .card-content > ha-input {
        margin-top: var(--ha-space-6);
      }
      ha-markdown {
        color: var(--primary-text-color);
      }
      /* ha-input keeps 8px below its field; with ha-form's 16px the fields are 24px apart, as inside ha-form */
      ha-form {
        display: block;
        margin-top: var(--ha-space-4);
      }
      .card-actions.split {
        justify-content: space-between;
      }
      ha-progress-bar,
      progress {
        display: block;
        width: 100%;
        margin-top: var(--ha-space-4);
      }
      p.status {
        margin: var(--ha-space-2) 0 var(--ha-space-4);
      }
      ha-alert {
        margin-bottom: var(--ha-space-4);
      }
      .panels {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-2);
        /* as the outlined expansion panel of Backups → Settings (no haStyle there) */
        line-height: normal;
      }
      /* step rows sit in the panel's default 0 8px content padding, like ha-backup-config-schedule's rows */
      sep-step-list {
        --ha-row-item-padding-inline: 0;
      }
      ha-expansion-panel.log {
        --expansion-panel-content-padding: 0;
      }
      /* the log keeps the line height of the Logs page (haStyle) */
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

define("sep-install-tab", SeInstallTab);

declare global {
  interface HTMLElementTagNameMap {
    "sep-install-tab": SeInstallTab;
  }
}
