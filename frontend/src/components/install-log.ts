import { LitElement, type PropertyValues, css, html } from "lit";
import { define } from "../ui";

export interface LogLine {
  /** `command`: "$ …" line, `output`: command output, `info`: step without a command, `warning`: non-fatal failure, `error`. */
  kind: "command" | "output" | "info" | "warning" | "error";
  text: string;
  /** Complete text when `text` is shortened for display (copy / download use it). */
  full?: string;
}

/** Log line of a command; very long commands (the ADB key) are shortened on screen. */
export const commandLine = (command: string): LogLine => {
  const full = `$ ${command}`;
  return full.length > 240
    ? { kind: "command", text: `${full.slice(0, 200)} … ${full.slice(-30)}`, full }
    : { kind: "command", text: full };
};

/** Plain text of a log (copy to clipboard / download). */
export const logText = (lines: LogLine[]): string => lines.map((l) => l.full ?? l.text).join("\n");

/**
 * Installer log, rendered like Home Assistant's own log view (Settings → System → Logs → raw
 * logs: `error-log-card` + `ha-ansi-to-html`): one wrapping `pre` with a `div` per line, in the
 * code font, errors in the error color; follows new lines while it is scrolled to the bottom.
 */
export class SeInstallLog extends LitElement {
  static properties = {
    lines: { attribute: false },
  };

  declare lines: LogLine[];

  private _follow = true;

  constructor() {
    super();
    this.lines = [];
  }

  private _onScroll(ev: Event): void {
    const el = ev.currentTarget as HTMLElement;
    this._follow = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
  }

  protected updated(changed: PropertyValues<this>): void {
    if (changed.has("lines") && this._follow) {
      const el = this.renderRoot.querySelector(".error-log");
      if (el) el.scrollTop = el.scrollHeight;
    }
  }

  render() {
    return html`<div class="error-log" role="log" @scroll=${this._onScroll}>
      ${this.lines.length
        ? html`<pre class="wrap">${this.lines.map((l) => html`<div class=${l.kind}>${l.text}</div>`)}</pre>`
        : html`<div>Waiting for the first step…</div>`}
    </div>`;
  }

  static styles = css`
    :host {
      display: block;
    }
    /* error-log-card */
    .error-log {
      position: relative;
      font-family: var(--ha-font-family-code);
      text-align: start;
      padding: var(--ha-space-4);
      overflow: auto;
      max-height: 320px;
      border-top: 1px solid var(--divider-color);
      direction: ltr;
      color: var(--primary-text-color);
    }
    /* ha-ansi-to-html */
    pre {
      margin: 0;
    }
    pre.wrap {
      white-space: pre-wrap;
      overflow-wrap: break-word;
    }
    .error {
      color: var(--error-color);
    }
    .warning {
      color: var(--warning-color);
    }
  `;
}

define("sep-install-log", SeInstallLog);

declare global {
  interface HTMLElementTagNameMap {
    "sep-install-log": SeInstallLog;
  }
}
