/** Which settings can currently be configured (`visible_if`, `requires`, `hidden` of the schema). */
import type { Capabilities, Requirement, SettingDef, SettingsGetResult, VisibleIf } from "./api";
import { formatValue } from "./ui";

/** A `visible_if` condition that does not hold, with the setting it refers to. */
export interface FailedCondition {
  cond: VisibleIf;
  parent?: SettingDef;
}

export interface Visibility {
  visible: boolean;
  /** `hidden: true` itself (never shown, not even as a search result). */
  hidden: boolean;
  /** A setting it depends on can never be shown. */
  unreachable: boolean;
  /** Capabilities the display lacks. */
  missing: Requirement[];
  /** Conditions that do not hold, the outermost parent first. */
  failed: FailedCondition[];
}

const SHOWN: Visibility = { visible: true, hidden: false, unreachable: false, missing: [], failed: [] };

/**
 * Equal like the app compares values: 1 equals 1.0 but true is not 1 and "1" is not 1. `loose` also
 * matches the string form ("true" equals true) for legacy displays, which may report strings.
 */
const sameValue = (a: unknown, b: unknown, loose = false): boolean =>
  JSON.stringify(a) === JSON.stringify(b) || (loose && a != null && b != null && String(a) === String(b));

/** Whether one `visible_if` condition holds; an unknown operator fails like in the app. */
export const conditionHolds = (cond: VisibleIf, value: unknown, loose = false): boolean => {
  if ("eq" in cond) return sameValue(value, cond.eq, loose);
  if ("ne" in cond) return !sameValue(value, cond.ne, loose);
  if (Array.isArray(cond.in)) return cond.in.some((v) => sameValue(value, v, loose));
  return false;
};

const requirementMet = (req: Requirement, caps: Capabilities, known: Set<string>): boolean => {
  // legacy displays and older apps do not report every capability
  if (!known.has(req.cap)) return true;
  const have: unknown = caps[req.cap];
  if (req.min !== undefined && req.min !== null) return typeof have === "number" && have >= req.min;
  if (typeof have === "boolean") return have;
  if (typeof have === "number") return have !== 0;
  if (typeof have === "string") return have !== "";
  return have != null;
};

/** Stand-in value of an unavailable setting: false for a bool and its default otherwise. */
const fallbackValue = (def: SettingDef): unknown => (def.type === "bool" ? false : def.default);

/** State of protocol v1 section 4 (ignores `hidden`) with the reasons for the hint. */
type State = Omit<Visibility, "visible" | "hidden"> & { state: "visible" | "unavailable" | "inactive" };

const VISIBLE_STATE: State = { state: "visible", unreachable: false, missing: [], failed: [] };

/**
 * Evaluates visibility against the current (edited) values like the app (SettingVisibility.java) and
 * the integration (api/visibility.py); build a new one when values change.
 */
export class VisibilityEvaluator {
  private readonly _defs = new Map<string, SettingDef>();
  private readonly _caps: Capabilities;
  private readonly _known: Set<string>;
  private readonly _loose: boolean;
  private readonly _cache = new Map<string, State>();

  constructor(
    data: SettingsGetResult,
    private readonly _value: (key: string) => unknown,
  ) {
    for (const def of data.schema) this._defs.set(def.key, def);
    this._caps = data.capabilities ?? {};
    this._known = new Set(data.known_caps ?? Object.keys(this._caps));
    this._loose = data.legacy ?? false;
  }

  def(key: string): SettingDef | undefined {
    return this._defs.get(key);
  }

  get(key: string): Visibility {
    const def = this._defs.get(key);
    if (!def) return SHOWN;
    if (def.hidden) return { ...SHOWN, visible: false, hidden: true };
    const { state, ...reasons } = this._state(def, new Set());
    return { ...reasons, visible: state === "visible", hidden: false };
  }

  visible(key: string): boolean {
    return this.get(key).visible;
  }

  /**
   * unavailable: a `requires` entry fails (checked first). inactive: a `visible_if` condition fails,
   * refers to an unknown or inactive setting or is part of a cycle. An unavailable parent counts as its
   * stand-in value. `hidden` only hides the setting itself.
   */
  private _state(def: SettingDef, visiting: Set<string>): State {
    const cached = this._cache.get(def.key);
    if (cached) return cached;
    const missing = (def.requires ?? []).filter((req) => !requirementMet(req, this._caps, this._known));
    if (missing.length) return this._store(def.key, { state: "unavailable", unreachable: false, missing, failed: [] });
    const conditions = def.visible_if ?? [];
    if (!conditions.length) return this._store(def.key, VISIBLE_STATE);
    // a cycle never resolves so every setting on it stays hidden
    if (visiting.has(def.key)) return { state: "inactive", unreachable: true, missing: [], failed: [] };
    visiting.add(def.key);
    const failed: FailedCondition[] = [];
    let unreachable = false;
    try {
      for (const cond of conditions) {
        const parent = this._defs.get(cond.key);
        if (!parent) {
          unreachable = true;
          continue;
        }
        const ref = this._state(parent, visiting);
        if (ref.state === "inactive") {
          // shown once the parent is shown and this condition holds
          missing.push(...ref.missing);
          failed.push(...ref.failed);
          unreachable ||= ref.unreachable;
          if (!conditionHolds(cond, this._current(parent), this._loose)) failed.push({ cond, parent });
        } else if (ref.state === "unavailable") {
          // a parent the display lacks cannot be switched to make this hold
          if (!conditionHolds(cond, fallbackValue(parent), this._loose)) missing.push(...ref.missing);
        } else if (!conditionHolds(cond, this._current(parent), this._loose)) {
          failed.push({ cond, parent });
        }
      }
    } finally {
      visiting.delete(def.key);
    }
    if (!missing.length && !failed.length && !unreachable) return this._store(def.key, VISIBLE_STATE);
    return this._store(def.key, { state: "inactive", unreachable, missing: dedupe(missing), failed: dedupe(failed) });
  }

  /** Current value of a setting, its default when unset. */
  private _current(def: SettingDef): unknown {
    const value = this._value(def.key);
    return value === undefined || value === null ? def.default : value;
  }

  private _store(key: string, state: State): State {
    this._cache.set(key, state);
    return state;
  }
}

const dedupe = <T>(items: T[]): T[] => {
  const seen = new Set<string>();
  return items.filter((item) => {
    const id = JSON.stringify(item);
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
};

const optionLabel = (parent: SettingDef | undefined, value: unknown): string =>
  parent?.options?.find((o) => sameValue(o.value, value, true))?.label ?? formatValue(value);

const describe = ({ cond, parent }: FailedCondition): string => {
  const label = parent?.label || cond.key;
  if ("eq" in cond) {
    if (typeof cond.eq === "boolean") return `${label} is ${cond.eq ? "on" : "off"}`;
    return `${label} is ${optionLabel(parent, cond.eq)}`;
  }
  if ("ne" in cond) {
    if (typeof cond.ne === "boolean") return `${label} is ${cond.ne ? "off" : "on"}`;
    return `${label} is not ${optionLabel(parent, cond.ne)}`;
  }
  return `${label} is ${(cond.in ?? []).map((v) => optionLabel(parent, v)).join(" or ")}`;
};

/** Why a setting is not shown, for search results ("Shown when Screensaver is on"). */
export const visibilityHint = (vis: Visibility): string => {
  if (vis.visible) return "";
  if (vis.missing.length || vis.unreachable || !vis.failed.length) return "Not available on this display";
  return `Shown when ${vis.failed.map(describe).join(" and ")}`;
};
