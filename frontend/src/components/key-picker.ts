import { LitElement, css, html } from "lit";
import { inputValue, isChecked, isDefined } from "../ha";
import { sharedStyles } from "../styles";
import { define } from "../ui";

export interface KeyOption {
  key: string;
  label?: string;
}

/** Filterable checkbox list of setting keys. Fires `selection-changed` with `{selected: Set<string>}`. */
export class SeKeyPicker extends LitElement {
  static properties = {
    options: { attribute: false },
    selected: { attribute: false },
    _filter: { state: true },
  };

  declare options: KeyOption[];
  declare selected: Set<string>;
  declare _filter: string;

  constructor() {
    super();
    this.options = [];
    this.selected = new Set();
    this._filter = "";
  }

  private _set(selected: Set<string>): void {
    this.selected = selected;
    this.dispatchEvent(new CustomEvent("selection-changed", { detail: { selected } }));
  }

  private _toggle(key: string, on: boolean): void {
    const next = new Set(this.selected);
    if (on) next.add(key);
    else next.delete(key);
    this._set(next);
  }

  private get _visible(): KeyOption[] {
    const f = this._filter.trim().toLowerCase();
    if (!f) return this.options;
    return this.options.filter((o) => o.key.toLowerCase().includes(f) || (o.label ?? "").toLowerCase().includes(f));
  }

  render() {
    const visible = this._visible;
    const onInput = (e: Event) => (this._filter = inputValue(e));
    return html`
      <div class="top">
        ${isDefined("ha-input-search")
          ? html`<ha-input-search appearance="outlined" .value=${this._filter} @input=${onInput}></ha-input-search>`
          : html`<ha-input .placeholder=${"Search"} .value=${this._filter} @input=${onInput}></ha-input>`}
        <ha-button
          appearance="plain"
          size="s"
          @click=${() => this._set(new Set([...this.selected, ...visible.map((o) => o.key)]))}
          >All</ha-button
        >
        <ha-button
          appearance="plain"
          size="s"
          @click=${() => {
            const hide = new Set(visible.map((o) => o.key));
            this._set(new Set([...this.selected].filter((k) => !hide.has(k))));
          }}
          >None</ha-button
        >
      </div>
      <div class="list">
        ${visible.map(
          (o) => html`
            <ha-checkbox .checked=${this.selected.has(o.key)} @change=${(e: Event) => this._toggle(o.key, isChecked(e))}>
              ${o.label || o.key}
              ${o.label && o.label !== o.key ? html`<span class="secondary">(${o.key})</span>` : ""}
            </ha-checkbox>
          `,
        )}
        ${visible.length ? "" : html`<div class="secondary pad">No matching settings.</div>`}
      </div>
      <div class="secondary count">${this.selected.size} of ${this.options.length} selected</div>
    `;
  }

  static styles = [
    sharedStyles,
    css`
      :host {
        display: block;
      }
      .top {
        display: flex;
        align-items: center;
        gap: var(--ha-space-1);
        margin-bottom: var(--ha-space-2);
      }
      .top > :first-child {
        flex: 1;
        min-width: 0;
      }
      /* ha-backup-addons-picker */
      .list {
        display: flex;
        flex-direction: column;
        gap: var(--ha-space-2);
        padding-inline-start: var(--ha-space-2);
        padding-bottom: var(--ha-space-3);
      }
      .pad {
        padding: var(--ha-space-2);
      }
      .count {
        margin-top: var(--ha-space-1);
        font-size: var(--ha-font-size-s);
      }
    `,
  ];
}

define("sep-key-picker", SeKeyPicker);

declare global {
  interface HTMLElementTagNameMap {
    "sep-key-picker": SeKeyPicker;
  }
}
