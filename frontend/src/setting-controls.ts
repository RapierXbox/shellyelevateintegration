/** Setting controls shared by the settings tab and the profile editor. */
import { css, html, nothing } from "lit";
import type { FileUpload, SettingDef } from "./api";
import { type SelectedEvent, inputValue, isChecked } from "./ha";
import { fileBase64, fileMatches, formatValue, pickFile, toast } from "./ui";

/** the display takes at most 512 KB per file */
export const MAX_UPLOAD = 512 * 1024;

export const CATEGORY_LABELS: Record<string, string> = {
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
export const CATEGORY_ORDER = Object.keys(CATEGORY_LABELS);

export const categoryLabel = (c: string): string => CATEGORY_LABELS[c] ?? c.charAt(0).toUpperCase() + c.slice(1);

/** Sort rank of a category: known ones in their order, the rest after them. */
export const categoryRank = (c: string): number => (CATEGORY_ORDER.includes(c) ? CATEGORY_ORDER.indexOf(c) : 99);

export const same = (a: unknown, b: unknown): boolean => JSON.stringify(a) === JSON.stringify(b);

/** Text shown in a text/number input for a value. */
export const toText = (def: SettingDef, value: unknown): string => {
  if (value === null || value === undefined) return "";
  if (def.type === "string_list") return Array.isArray(value) ? value.join(", ") : String(value);
  return String(value);
};

/** Parse input text -> [ok, value]. */
export const parseText = (def: SettingDef, text: string): [boolean, unknown] => {
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

/** "min – max unit" of a number setting, or "". */
export const rangeText = (def: SettingDef): string =>
  (def.type === "int" || def.type === "float") && (def.min != null || def.max != null)
    ? `${def.min ?? "…"} – ${def.max ?? "…"}${def.unit ? ` ${def.unit}` : ""}`
    : "";

export interface ControlOptions {
  value: unknown;
  /** Text of a number or list input while it is edited (may not parse yet). */
  text?: string;
  invalid?: boolean;
  disabled?: boolean;
  secret?: boolean;
  onValue: (value: unknown) => void;
  onText: (text: string) => void;
}

/** The control of a setting that is not a file setting (those differ between callers). */
export const renderSettingControl = (def: SettingDef, o: ControlOptions) => {
  const label = def.label ?? def.key;
  const disabled = !!o.disabled;
  switch (def.type) {
    case "bool":
      return html`<ha-switch
        .checked=${o.value === true}
        .disabled=${disabled}
        aria-label=${label}
        @change=${(e: Event) => o.onValue(isChecked(e))}
      ></ha-switch>`;
    case "enum": {
      const options = def.options ?? [];
      const idx = options.findIndex((opt) => same(opt.value, o.value) || String(opt.value) === String(o.value));
      const items = options.map((opt, i) => ({ value: String(i), label: opt.label }));
      if (idx < 0) items.unshift({ value: "-1", label: formatValue(o.value) });
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
          if (i >= 0 && options[i]) o.onValue(options[i].value);
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
        .invalid=${!!o.invalid}
        .min=${def.min ?? undefined}
        .max=${def.max ?? undefined}
        .step=${def.step ?? (def.type === "int" ? 1 : "any")}
        .value=${o.text ?? toText(def, o.value)}
        @input=${(e: Event) => o.onText(inputValue(e))}
      >
        ${def.unit ? html`<span slot="end" class="unit">${def.unit}</span>` : nothing}
      </ha-input>`;
    case "string_list": {
      const options = def.options ?? [];
      if (options.length) {
        // a list with options: the chosen ones as chips and a select that adds one more
        const chosen = Array.isArray(o.value) ? (o.value as unknown[]).map(String) : [];
        const rest = options.filter((opt) => !chosen.includes(String(opt.value)));
        const labelOf = (v: string) => options.find((opt) => String(opt.value) === v)?.label ?? v;
        const items = [{ value: "-1", label: "+ Add" }, ...rest.map((opt, i) => ({ value: String(i), label: opt.label }))];
        return html`<div class="ctrl" style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;justify-content:flex-end">
          ${chosen.map(
            (v) =>
              html`<span
                style="display:inline-flex;align-items:center;gap:4px;padding:2px 4px 2px 10px;border-radius:14px;background:var(--secondary-background-color);font-size:0.9em"
                >${labelOf(v)}<button
                  type="button"
                  style="border:none;background:none;color:inherit;cursor:pointer;font-size:1.1em;line-height:1;padding:2px 6px"
                  aria-label=${`Remove ${labelOf(v)}`}
                  .disabled=${disabled}
                  @click=${() => o.onValue(chosen.filter((c) => c !== v))}
                >
                  ×
                </button></span
              >`,
          )}
          ${rest.length
            ? html`<ha-select
                .label=${undefined}
                aria-label=${label}
                .options=${items}
                .value=${"-1"}
                .disabled=${disabled}
                @selected=${(e: SelectedEvent) => {
                  e.stopPropagation();
                  const i = Number(e.detail.value);
                  // back to the add entry so the same select adds the next one
                  (e.target as HTMLElement & { value: string }).value = "-1";
                  if (i >= 0 && rest[i]) o.onValue([...chosen, String(rest[i].value)]);
                }}
              ></ha-select>`
            : nothing}
        </div>`;
      }
      return html`<ha-input
        class="ctrl"
        .disabled=${disabled}
        aria-label=${label}
        placeholder="value1, value2"
        .value=${o.text ?? toText(def, o.value)}
        @input=${(e: Event) => o.onText(inputValue(e))}
      ></ha-input>`;
    }
    default:
      return html`<ha-input
        class="ctrl"
        .disabled=${disabled}
        aria-label=${label}
        .type=${o.secret ? "password" : "text"}
        ?password-toggle=${o.secret}
        autocomplete=${o.secret ? "new-password" : "off"}
        .value=${o.value === null || o.value === undefined ? "" : String(o.value)}
        @input=${(e: Event) => o.onValue(inputValue(e))}
      ></ha-input>`;
  }
};

/** Pick the file of a file setting; null when cancelled or not usable (a toast says why). */
export const pickUpload = async (el: HTMLElement, def: SettingDef): Promise<FileUpload | null> => {
  const accept = def.accept ?? "*/*";
  const file = await pickFile(accept);
  if (!file) return null;
  if (!fileMatches(file, accept)) {
    toast(el, `${file.name} is not ${accept.startsWith("audio/") ? "an audio file" : "a supported file"}`, "error");
    return null;
  }
  if (file.size > MAX_UPLOAD) {
    toast(el, `${file.name} is larger than 512 KB`, "error");
    return null;
  }
  return { name: file.name, data_b64: await fileBase64(file) };
};

/** A row with its control at the end: ha-backup-config-schedule. */
export const settingRowStyles = css`
  .end {
    display: flex;
    align-items: center;
  }
  .end ha-select {
    min-width: 210px;
  }
  .file-name {
    max-width: 160px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--secondary-text-color);
  }
  .end ha-input {
    width: 210px;
    /* no space reserved for a hint (errors are shown in the supporting text): 56px like ha-select */
    --ha-input-padding-bottom: 0;
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
`;
