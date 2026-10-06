/** Small UI helpers shared by all tabs, and the events the tabs send to the root panel. */
import type { TemplateResult } from "lit";
import { errorMessage } from "./api";
import { fireEvent, showToast } from "./ha";

export type TabId = "displays" | "install" | "settings" | "profiles" | "backups";

export type ToastLevel = "info" | "success" | "warning" | "error";

export interface ConfirmOptions {
  title: string;
  text?: string | TemplateResult;
  /** Bullet list shown below the text. */
  items?: string[];
  confirmText?: string;
  dismissText?: string;
  destructive?: boolean;
  /** Information only: a single OK button. */
  alert?: boolean;
}

export interface ConfirmDetail extends ConfirmOptions {
  resolve: (ok: boolean) => void;
}

export interface OpenTabDetail {
  tab: TabId;
  entryId?: string;
}

/** Events handled by the root panel (all bubble and are composed). */
declare global {
  interface HTMLElementEventMap {
    "se-confirm": CustomEvent<ConfirmDetail>;
    "se-open-tab": CustomEvent<OpenTabDetail>;
    "se-refresh-devices": CustomEvent<undefined>;
    "se-revert": CustomEvent<RevertTarget>;
    "se-entry-selected": CustomEvent<{ entryId: string }>;
    /** Unsaved changes of the Settings tab, null when there are none. */
    "se-unsaved": CustomEvent<{ count: number; name: string } | null>;
  }
}

/**
 * The mounted panel. Tabs are removed when another tab is opened, so the result of a slow
 * action (toast, confirm) is sent from the panel when the tab that started it is gone.
 */
let eventRoot: HTMLElement | null = null;

export const setEventRoot = (el: HTMLElement | null): void => {
  eventRoot = el;
};

/** `el` while it is in the document, otherwise the panel. */
const source = (el: HTMLElement): HTMLElement => (el.isConnected || !eventRoot?.isConnected ? el : eventRoot);

/** Register a custom element once (the panel module may be evaluated more than once). */
export const define = (name: string, ctor: CustomElementConstructor): void => {
  if (!customElements.get(name)) customElements.define(name, ctor);
};

/** Ask the root panel to show a confirm dialog. */
export const confirmDialog = (el: HTMLElement, options: ConfirmOptions): Promise<boolean> =>
  new Promise((resolve) => {
    const notHandled = source(el).dispatchEvent(
      new CustomEvent<ConfirmDetail>("se-confirm", {
        detail: { ...options, resolve },
        bubbles: true,
        composed: true,
        cancelable: true,
      }),
    );
    // Not handled by the panel (e.g. `el` was removed by a tab switch): use the native dialog.
    if (notHandled) {
      const text = typeof options.text === "string" ? options.text : "";
      resolve(window.confirm(`${options.title}\n\n${text}\n${(options.items ?? []).join("\n")}`));
    }
  });

/**
 * Show a message in Home Assistant's toast. Details (e.g. per-display errors) are available
 * through a "Details" action that opens a dialog.
 */
export const toast = (el: HTMLElement, message: string, level: ToastLevel = "info", details?: string[]): void => {
  const duration = level === "error" ? 10000 : details?.length ? 8000 : 4000;
  showToast(source(el), {
    message,
    duration,
    dismissable: true,
    action: details?.length
      ? {
          text: "Details",
          action: () => {
            confirmDialog(el, { title: message, items: details, alert: true });
          },
        }
      : undefined,
  });
};

/** Error toast: "`prefix`: `message of err`" (just the message without prefix). */
export const toastError = (el: HTMLElement, prefix: string, err: unknown): void =>
  toast(el, prefix ? `${prefix}: ${errorMessage(err)}` : errorMessage(err), "error");

export const openTab = (el: HTMLElement, tab: TabId, entryId?: string): void =>
  fireEvent<OpenTabDetail>(el, "se-open-tab", { tab, entryId });

export const refreshDevices = (el: HTMLElement): void => fireEvent(el, "se-refresh-devices");

/** Display to revert: a configured one (entry id and name known) or any address. */
export interface RevertTarget {
  /** Checked right away. */
  host?: string;
  /** Without `host`: the address field starts with this value. */
  prefill?: string;
  entryId?: string;
  name?: string;
}

/** Open the "Revert to stock" dialog of the root panel. */
export const openRevert = (el: HTMLElement, target: RevertTarget = {}): void =>
  fireEvent<RevertTarget>(el, "se-revert", target);

const ANDROID_VERSIONS: Record<number, string> = {
  24: "7.0",
  25: "7.1",
  26: "8.0",
  27: "8.1",
  28: "9",
  29: "10",
  30: "11",
  31: "12",
  32: "12L",
  33: "13",
  34: "14",
  35: "15",
  36: "16",
};

/** "Android 11 (API 30)", "Android API 23", or "" when unknown. */
export const androidVersion = (sdk: number | null | undefined): string => {
  if (typeof sdk !== "number") return "";
  const name = ANDROID_VERSIONS[sdk];
  return name ? `Android ${name} (API ${sdk})` : `Android API ${sdk}`;
};

/** Select the display shown in the Settings and Backups tabs. */
export const selectEntry = (el: HTMLElement, entryId: string): void => fireEvent(el, "se-entry-selected", { entryId });

export const downloadJson = (filename: string, data: unknown): void =>
  downloadBlob(filename, new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));

export const downloadText = (filename: string, text: string): void =>
  downloadBlob(filename, new Blob([text], { type: "text/plain" }));

const downloadBlob = (filename: string, blob: Blob): void => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

/** Let the user pick a file; resolves with null when cancelled. */
export const pickFile = (accept: string): Promise<File | null> =>
  new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = accept;
    input.addEventListener("change", () => resolve(input.files?.[0] ?? null), { once: true });
    input.addEventListener("cancel", () => resolve(null), { once: true });
    input.click();
  });

export const slug = (value: string): string =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "display";

export const formatDate = (iso: string | null | undefined, language?: string): string => {
  if (!iso) return "–";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(language || undefined, { dateStyle: "medium", timeStyle: "short" });
};

/** Compact display of a setting value in diffs and tables. */
export const formatValue = (value: unknown): string => {
  if (value === undefined) return "–";
  if (value === null) return "null";
  if (value === "**REDACTED**") return "••••";
  if (typeof value === "string") return value === "" ? '""' : value;
  return JSON.stringify(value);
};

export const plural = (n: number, one: string, many = `${one}s`): string => `${n} ${n === 1 ? one : many}`;

export const isPlainObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

/** Stop clicks inside a clickable row (menus, buttons) from reaching the row. */
export const stopPropagation = (ev: Event): void => ev.stopPropagation();
