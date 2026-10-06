import { LitElement, css, html, nothing } from "lit";
import type { DiffItem } from "../api";
import { isChecked } from "../ha";
import { sharedStyles } from "../styles";
import { define, formatValue } from "../ui";

/**
 * Shows a settings diff (key, current → new). With `selectable`, every row gets a checkbox and
 * `selected` holds the checked keys (fires `selection-changed` with `{selected: Set<string>}`).
 */
export class SeDiffTable extends LitElement {
  static properties = {
    diff: { attribute: false },
    selectable: { type: Boolean },
    selected: { attribute: false },
    emptyText: { attribute: "empty-text" },
  };

  declare diff: DiffItem[];
  declare selectable: boolean;
  declare selected: Set<string>;
  declare emptyText: string;

  constructor() {
    super();
    this.diff = [];
    this.selectable = false;
    this.selected = new Set();
    this.emptyText = "No changes – already up to date.";
  }

  private _toggle(key: string, on: boolean): void {
    const next = new Set(this.selected);
    if (on) next.add(key);
    else next.delete(key);
    this._emit(next);
  }

  private _emit(selected: Set<string>): void {
    this.selected = selected;
    this.dispatchEvent(new CustomEvent("selection-changed", { detail: { selected } }));
  }

  private _renderSelectAll() {
    const all = this.diff.every((d) => this.selected.has(d.key));
    return html`<ha-list-item-base>
      <ha-checkbox
        slot="start"
        .checked=${all}
        .indeterminate=${!all && this.selected.size > 0}
        @change=${(e: Event) => this._emit(isChecked(e) ? new Set(this.diff.map((d) => d.key)) : new Set())}
      ></ha-checkbox>
      <span slot="headline">Select all</span>
      <span slot="end" class="secondary">${this.selected.size} of ${this.diff.length}</span>
    </ha-list-item-base>`;
  }

  /** Changed settings as list rows: key, "current → new". */
  render() {
    if (!this.diff.length) return html`<p>${this.emptyText}</p>`;
    return html`
      <ha-list-base class="rows" aria-label="Changes">
        ${this.selectable ? this._renderSelectAll() : nothing}
        ${this.diff.map(
          (item) => html`
            <ha-list-item-base>
              ${this.selectable
                ? html`<ha-checkbox
                    slot="start"
                    .checked=${this.selected.has(item.key)}
                    @change=${(e: Event) => this._toggle(item.key, isChecked(e))}
                  ></ha-checkbox>`
                : nothing}
              <span slot="headline">${item.key}</span>
              <span slot="supporting-text">${formatValue(item.current)} → ${formatValue(item.new)}</span>
            </ha-list-item-base>
          `,
        )}
      </ha-list-base>
    `;
  }

  static styles = [
    sharedStyles,
    css`
      :host {
        display: block;
      }
      p {
        margin: var(--ha-space-2) 0;
      }
    `,
  ];
}

define("sep-diff-table", SeDiffTable);

declare global {
  interface HTMLElementTagNameMap {
    "sep-diff-table": SeDiffTable;
  }
}
