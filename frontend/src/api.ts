/** Typed wrappers around the `shellyelevateintegration/...` websocket commands (see websocket.py). */
import type { HomeAssistant, UnsubscribeFunc } from "./ha";

// --------------------------------------------------------------------------- models

export interface DeviceSummary {
  entry_id: string;
  /** Home Assistant device registry id (not the display's own id). */
  device_id?: string | null;
  /** The display's own id; backups are stored under it. */
  display_id?: string;
  name: string;
  model?: string;
  sku?: string | null;
  fw_version?: string | null;
  api_version?: string | null;
  host?: string;
  legacy?: boolean;
  available: boolean;
  adb?: boolean;
  /** Only present when the entry is loaded. */
  capabilities?: Capabilities;
  /** Config entry state, only present when the entry is not loaded. */
  state?: string;
}

export const isLoaded = (device: DeviceSummary): boolean => device.state === undefined;

/** Name of a display, falling back to the entry id. */
export const deviceName = (devices: DeviceSummary[], entryId: string): string =>
  devices.find((d) => d.entry_id === entryId)?.name ?? entryId;

export type SettingType = "bool" | "int" | "float" | "string" | "enum" | "string_list";

export interface SettingOption {
  value: unknown;
  label: string;
}

/** Counts (relays, inputs, buttons) and flags (proximity, speaker, ...) of a display. */
export type Capabilities = Record<string, number | boolean | null>;

/** `visible_if` condition: the value of another setting equals / differs from / is one of. */
export interface VisibleIf {
  key: string;
  eq?: unknown;
  ne?: unknown;
  in?: unknown[];
}

/** `requires` entry: a capability that is truthy, or at least `min`. */
export interface Requirement {
  cap: string;
  min?: number;
}

export interface SettingDef {
  key: string;
  type: SettingType | string;
  default?: unknown;
  label?: string | null;
  description?: string | null;
  category?: string | null;
  min?: number | null;
  max?: number | null;
  step?: number | null;
  unit?: string | null;
  options?: SettingOption[] | null;
  secret?: boolean;
  per_device?: boolean;
  requires_restart?: boolean;
  /** Belongs to a feature the app will remove. */
  deprecated?: boolean;
  /** Key of the setting that replaces it. */
  replaced_by?: string | null;
  /** Shown only while all conditions hold. */
  visible_if?: VisibleIf[] | null;
  /** Shown only on displays with these capabilities. */
  requires?: Requirement[] | null;
  /** Never shown. */
  hidden?: boolean;
  /** Shown but not editable. */
  read_only?: boolean;
}

export type Settings = Record<string, unknown>;

export interface SettingsGetResult {
  settings: Settings;
  schema: SettingDef[];
  per_device: string[];
  secret: string[];
  capabilities?: Capabilities;
  /** Capabilities the display reports; `requires` on any other one counts as met. */
  known_caps?: string[];
  /** Settings the integration controls itself (key -> reason), shown read-only. */
  managed?: Record<string, string>;
  /** Legacy app: values may be strings so conditions compare them loosely. */
  legacy?: boolean;
}

export interface SettingsSetResult {
  settings: Settings;
  /** Keys the display does not know: nothing was written for them. */
  ignored?: string[];
}

/** Keys that are never copied between displays (IDs, names, ...). */
export const perDeviceKeys = (data: SettingsGetResult): Set<string> =>
  new Set([...data.per_device, ...data.schema.filter((d) => d.per_device).map((d) => d.key)]);

export interface DiffItem {
  key: string;
  current: unknown;
  new: unknown;
}

export interface SettingsExport {
  format: string;
  exported: string;
  device: { id: string; name: string; model?: string | null; fw?: string | null };
  settings: Settings;
}

export interface Profile {
  id: string;
  name: string;
  settings: Settings;
  created?: string;
  updated?: string;
  default: boolean;
}

export interface Backup {
  id: string;
  created: string;
  reason: string;
  name?: string | null;
  fw_version?: string | null;
  model?: string | null;
  settings: Settings;
}

export interface CommandResult {
  ok: boolean;
  data?: unknown;
  error?: string;
}

export interface ApplyResult {
  results: Record<string, DiffItem[]>;
  errors: Record<string, string>;
}

export interface Release {
  version: string;
  prerelease: boolean;
  published?: string | null;
}

export interface InstallerInfo {
  releases: Release[];
  profiles: Profile[];
  default_profile: string | null;
  dashboard_url: string | null;
}

export type StepStatus = "pending" | "running" | "done" | "failed";

/** Progress of one installer step; the extra fields depend on the step. */
export interface StepEvent {
  type: "step";
  step: string;
  status: StepStatus;
  error?: string;
  root?: boolean;
  /** root_check / check: Android API level of the display (null when unknown). */
  sdk?: number | null;
  version?: string | null;
  bytes?: number;
  legacy?: boolean;
  /** config_entry: the display was already configured and its entry was updated. */
  updated?: boolean;
  /** ADB steps: the shell command (`running`) and the end of its output (`done`). */
  command?: string;
  output?: string;
}

export interface InstallerDoneEvent {
  type: "done";
  entry_id?: string | null;
  /** Home Assistant device registry id (null until the entry has been set up). */
  device_id?: string | null;
  /** The display's own id. */
  display_id?: string;
  legacy?: boolean;
  name?: string;
}

export type InstallerEvent = StepEvent | InstallerDoneEvent | { type: "error"; error: string };

export interface ProvisionOptions {
  install_app: boolean;
  channel: "stable" | "beta";
  /** A specific release to install; null = the latest of `channel`. */
  version: string | null;
  /** Keep the stock Shelly app from covering Shelly Elevate (see post_install_commands). */
  disable_stock: boolean;
  profile_id: string | null;
  dashboard_url: string | null;
}

// revert to stock

/** What `revert/check` found on the display (see adb/steps.py RevertCheck). */
export interface RevertFindings {
  app_installed: boolean;
  /** A copy of the app in /system/priv-app. */
  priv_app: boolean;
  /** A startup script in /system (old root installs). */
  init_rc: boolean;
  stock_installed: boolean;
  stock_disabled: boolean;
  /** Disabled as root (`pm disable`); enabling it again needs root. */
  stock_disabled_by_root: boolean;
  /** Home activity of the stock app, e.g. "cloud.shelly.stargate/.MainActivity". */
  stock_home: string | null;
  /** The old ShellyElevate V1 app. */
  legacy_v1: boolean;
  /** Ultra Small Launcher (from the community wiki guide). */
  wiki_launcher: boolean;
  /** The display's Wi-Fi network was created by the app (uninstalling removes it). */
  wifi_by_app: boolean;
  /** The installer's APK is still in /data/local/tmp. */
  leftover_apk: boolean;
}

export type RevertWarning = "wifi_by_app" | "stock_needs_root" | "system_copy_needs_root" | "stock_missing" | "no_baseline";

/** What is still there after the revert: the app, its /system copy, a disabled stock app. */
export type RevertRemaining = "app" | "system_copy" | "stock_disabled";

export interface RevertCheckResult {
  platform: { sdk: number | null; model: string | null; root: boolean };
  check: RevertFindings;
  warnings: (RevertWarning | string)[];
  /** The display's config entry, when it is set up in Home Assistant. */
  entry_id: string | null;
  name: string | null;
}

export interface RevertOptions {
  remove_entry: boolean;
  reboot: boolean;
  disable_adb: boolean;
  remove_wiki_launcher: boolean;
  accept_wifi_loss: boolean;
}

export interface RevertStepEvent extends StepEvent {
  /** verify: what could not be removed. */
  remaining?: RevertRemaining[];
}

export interface RevertDoneEvent {
  type: "done";
  remaining: (RevertRemaining | string)[];
  entry_removed: boolean;
  adb_disabled: boolean;
  warnings: (RevertWarning | string)[];
}

export type RevertEvent = RevertStepEvent | RevertDoneEvent | { type: "error"; error: string };

// --------------------------------------------------------------------------- api

const PREFIX = "shellyelevateintegration";

export class ElevateApi {
  /** Takes a getter because Home Assistant replaces the `hass` object on every state change. */
  constructor(private readonly getHass: () => HomeAssistant) {}

  get hass(): HomeAssistant {
    return this.getHass();
  }

  private ws<T>(type: string, params: Record<string, unknown> = {}): Promise<T> {
    return this.hass.callWS<T>({ type: `${PREFIX}/${type}`, ...params });
  }

  // devices / settings
  async devices(): Promise<DeviceSummary[]> {
    return (await this.ws<{ devices: DeviceSummary[] }>("devices")).devices;
  }

  settingsGet(entryId: string): Promise<SettingsGetResult> {
    return this.ws("settings/get", { entry_id: entryId });
  }

  settingsSet(entryId: string, changes: Settings): Promise<SettingsSetResult> {
    return this.ws("settings/set", { entry_id: entryId, changes });
  }

  /** Setting changes of one display as they happen (from Home Assistant or on the display). */
  subscribeSettings(entryId: string, callback: (changes: Settings) => void): Promise<UnsubscribeFunc> {
    return this.hass.connection.subscribeMessage<{ changes: Settings }>(
      (event) => callback(event.changes),
      { type: `${PREFIX}/settings/subscribe`, entry_id: entryId },
      { resubscribe: true },
    );
  }

  settingsExport(entryId: string, includeSecrets: boolean): Promise<SettingsExport> {
    return this.ws("settings/export", { entry_id: entryId, include_secrets: includeSecrets });
  }

  /** Results are keyed by the target's HA device id. */
  /**
   * `results` and `errors` are keyed by the target's HA device id. A target that failed (offline,
   * rejected) is in `errors` only; the others were still copied.
   */
  async settingsCopy(
    source: string,
    targets: string[],
    keys?: string[],
  ): Promise<{ results: Record<string, DiffItem[]>; errors: Record<string, string> }> {
    const params: Record<string, unknown> = { source, targets };
    if (keys?.length) params.keys = keys;
    const response = await this.ws<{ results: Record<string, DiffItem[]>; errors?: Record<string, string> }>(
      "settings/copy",
      params,
    );
    return { results: response.results, errors: response.errors ?? {} };
  }

  async command(
    entryIds: string[],
    action: string,
    params: Record<string, unknown> = {},
  ): Promise<Record<string, CommandResult>> {
    return (
      await this.ws<{ results: Record<string, CommandResult> }>("command", { entry_ids: entryIds, action, params })
    ).results;
  }

  // backups
  /** Keyed by the display's own id (store key), not the HA device id. */
  async backupsList(entryId?: string): Promise<Record<string, Backup[]>> {
    return (await this.ws<{ backups: Record<string, Backup[]> }>("backups/list", entryId ? { entry_id: entryId } : {}))
      .backups;
  }

  async backupsCreate(entryId: string, name?: string): Promise<Backup> {
    return (await this.ws<{ backup: Backup }>("backups/create", name ? { entry_id: entryId, name } : { entry_id: entryId }))
      .backup;
  }

  async backupsDiff(entryId: string, backupId: string, sourceDisplayId?: string): Promise<DiffItem[]> {
    const params: Record<string, unknown> = { entry_id: entryId, backup_id: backupId };
    if (sourceDisplayId) params.source_device_id = sourceDisplayId;
    return (await this.ws<{ diff: DiffItem[] }>("backups/diff", params)).diff;
  }

  async backupsRestore(entryId: string, backupId: string, keys?: string[], sourceDisplayId?: string): Promise<DiffItem[]> {
    const params: Record<string, unknown> = { entry_id: entryId, backup_id: backupId };
    if (keys) params.keys = keys;
    if (sourceDisplayId) params.source_device_id = sourceDisplayId;
    return (await this.ws<{ changes: DiffItem[] }>("backups/restore", params)).changes;
  }

  async backupsDelete(displayId: string, backupId: string): Promise<void> {
    await this.ws("backups/delete", { device_id: displayId, backup_id: backupId });
  }

  // profiles
  profilesList(): Promise<{ profiles: Profile[]; default: string | null }> {
    return this.ws("profiles/list");
  }

  async profilesSave(params: {
    name: string;
    profile_id?: string;
    settings?: Settings;
    from_entry_id?: string;
    keys?: string[];
    make_default?: boolean;
  }): Promise<string> {
    const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined));
    return (await this.ws<{ profile_id: string }>("profiles/save", clean)).profile_id;
  }

  async profilesDelete(profileId: string): Promise<void> {
    await this.ws("profiles/delete", { profile_id: profileId });
  }

  async profilesSetDefault(profileId: string | null): Promise<void> {
    await this.ws("profiles/set_default", { profile_id: profileId });
  }

  /**
   * dry_run: `results` maps entry_id -> diff; otherwise entry_id -> applied changes. Displays
   * that failed are in `errors` (entry_id -> message) and not in `results`.
   */
  async profilesApply(profileId: string, entryIds: string[], dryRun: boolean): Promise<ApplyResult> {
    const res = await this.ws<{ results?: Record<string, DiffItem[]>; errors?: Record<string, string> }>(
      "profiles/apply",
      { profile_id: profileId, entry_ids: entryIds, dry_run: dryRun },
    );
    return { results: res.results ?? {}, errors: res.errors ?? {} };
  }

  // installer
  installerInfo(): Promise<InstallerInfo> {
    return this.ws("installer/info");
  }

  subscribeProvision(
    host: string,
    options: ProvisionOptions,
    callback: (event: InstallerEvent) => void,
  ): Promise<UnsubscribeFunc> {
    return this.hass.connection.subscribeMessage<InstallerEvent>(
      callback,
      {
        type: `${PREFIX}/installer/provision`,
        host,
        ...options,
        profile_id: options.profile_id || null,
        dashboard_url: options.dashboard_url?.trim() || null,
      },
      { resubscribe: false },
    );
  }

  // revert
  revertCheck(host: string): Promise<RevertCheckResult> {
    return this.ws("revert/check", { host });
  }

  /** Runs the revert; unsubscribing cancels it. */
  subscribeRevert(host: string, options: RevertOptions, callback: (event: RevertEvent) => void): Promise<UnsubscribeFunc> {
    return this.hass.connection.subscribeMessage<RevertEvent>(
      callback,
      { type: `${PREFIX}/revert/run`, host, ...options },
      { resubscribe: false },
    );
  }
}

/** Human readable message of a websocket error / exception. */
export const errorMessage = (err: unknown): string => {
  if (!err) return "Unknown error";
  if (typeof err === "string") return err;
  if (typeof err === "object") {
    const e = err as { message?: unknown; error?: unknown; code?: unknown };
    if (typeof e.message === "string" && e.message) return e.message;
    if (typeof e.error === "string" && e.error) return e.error;
    if (typeof e.code === "string") return e.code;
  }
  return String(err);
};
