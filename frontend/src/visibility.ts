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

const sameValue = (a: unknown, b: unknown): boolean =>
  JSON.stringify(a) === JSON.stringify(b) || (a != null && b != null && String(a) === String(b));

export const conditionHolds = (cond: VisibleIf, value: unknown): boolean => {
  if ("eq" in cond) return sameValue(value, cond.eq);
  if ("ne" in cond) return !sameValue(value, cond.ne);
  if (Array.isArray(cond.in)) return cond.in.some((v) => sameValue(value, v));
  return true;
};

const requirementMet = (req: Requirement, caps: Capabilities, known: Set<string>): boolean => {
  // legacy displays and older apps do not report every capability
  if (!known.has(req.cap)) return true;
  const have = caps[req.cap];
  if (req.min !== undefined && req.min !== null) return Number(have ?? 0) >= req.min;
  return !!have;
};

/** What a condition compares against: a value, or the reasons its setting is not shown. */
type RefState = { value: unknown; missing?: Requirement[] } | { blocked: Visibility };

/** Evaluates visibility against the current (edited) values; build a new one when values change. */
export class VisibilityEvaluator {
  private readonly _defs = new Map<string, SettingDef>();
  private readonly _caps: Capabilities;
  private readonly _known: Set<string>;
  private readonly _cache = new Map<string, Visibility>();

  constructor(
    data: SettingsGetResult,
    private readonly _value: (key: string) => unknown,
  ) {
    for (const def of data.schema) this._defs.set(def.key, def);
    this._caps = data.capabilities ?? {};
    this._known = new Set(data.known_caps ?? Object.keys(this._caps));
  }

  def(key: string): SettingDef | undefined {
    return this._defs.get(key);
  }

  get(key: string): Visibility {
    return this._eval(key, new Set());
  }

  visible(key: string): boolean {
    return this.get(key).visible;
  }

  private _eval(key: string, stack: Set<string>): Visibility {
    const cached = this._cache.get(key);
    if (cached) return cached;
    const def = this._defs.get(key);
    if (!def) return SHOWN;
    if (def.hidden) return this._store(key, { ...SHOWN, visible: false, hidden: true });
    const missing = (def.requires ?? []).filter((req) => !requirementMet(req, this._caps, this._known));
    const failed: FailedCondition[] = [];
    let unreachable = false;
    stack.add(key);
    for (const cond of def.visible_if ?? []) {
      const ref = this._refState(cond.key, stack);
      if ("blocked" in ref) {
        // the parent is not shown itself so report why and then this condition
        missing.push(...ref.blocked.missing);
        failed.push(...ref.blocked.failed);
        unreachable ||= ref.blocked.hidden || ref.blocked.unreachable;
        if (!conditionHolds(cond, this._current(cond.key))) failed.push({ cond, parent: this._defs.get(cond.key) });
      } else if (!conditionHolds(cond, ref.value)) {
        // a parent the display cannot use cannot be switched to make this hold
        if (ref.missing?.length) missing.push(...ref.missing);
        else failed.push({ cond, parent: this._defs.get(cond.key) });
      }
    }
    stack.delete(key);
    if (!missing.length && !failed.length && !unreachable) return this._store(key, SHOWN);
    return this._store(key, {
      visible: false,
      hidden: false,
      unreachable,
      missing: dedupe(missing),
      failed: dedupe(failed),
    });
  }

  /**
   * The value a condition on `key` is checked against.
   * A parent that is only missing a capability counts as off (bool) or its default value like the app.
   * `hidden` only hides the parent itself; a parent hidden by its own conditions hides the child too.
   * Cycles fall back to the current value.
   */
  private _refState(key: string, stack: Set<string>): RefState {
    const parent = this._defs.get(key);
    if (!parent || stack.has(key) || parent.hidden) return { value: this._current(key) };
    const vis = this._eval(key, stack);
    if (vis.visible) return { value: this._current(key) };
    if (!vis.unreachable && !vis.failed.length) {
      return { value: parent.type === "bool" ? false : parent.default, missing: vis.missing };
    }
    return { blocked: vis };
  }

  private _current(key: string): unknown {
    const value = this._value(key);
    return value === undefined ? this._defs.get(key)?.default : value;
  }

  private _store(key: string, vis: Visibility): Visibility {
    this._cache.set(key, vis);
    return vis;
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
  parent?.options?.find((o) => sameValue(o.value, value))?.label ?? formatValue(value);

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
