import { LitElement, css, html, nothing } from "lit";
import { keyed } from "lit/directives/keyed.js";
import { mdiAlert, mdiAlertCircle, mdiCheckCircle, mdiCircleOutline, mdiMinusCircleOutline } from "@mdi/js";
import type { StepStatus } from "../api";
import { sharedStyles } from "../styles";
import { define } from "../ui";

export interface StepState {
  id: string;
  label: string;
  status: StepStatus | "skipped" | "warning";
  detail?: string;
}

const ICONS: Record<Exclude<StepState["status"], "running">, string> = {
  done: mdiCheckCircle,
  failed: mdiAlertCircle,
  warning: mdiAlert,
  skipped: mdiMinusCircleOutline,
  pending: mdiCircleOutline,
};

/** Installation progress as an HA list: spinner / status icon, label and detail per step. */
export class SeStepList extends LitElement {
  static properties = {
    steps: { attribute: false },
  };

  declare steps: StepState[];

  constructor() {
    super();
    this.steps = [];
  }

  render() {
    // ha-list-item-base only shows the supporting-text slot if it had content when it first
    // rendered, so a step gets a new item once it has a detail.
    return html`
      <ha-list-base aria-label="Installation steps">
        ${this.steps.map((step) =>
          keyed(
            !!step.detail,
            html`<ha-list-item-base class=${step.status}>
              <span slot="start" class="ico">
                ${step.status === "running"
                  ? html`<ha-spinner size="tiny"></ha-spinner>`
                  : html`<ha-svg-icon .path=${ICONS[step.status]}></ha-svg-icon>`}
              </span>
              <span slot="headline">${step.label}</span>
              ${step.detail ? html`<span slot="supporting-text" class="detail">${step.detail}</span>` : nothing}
            </ha-list-item-base>`,
          ),
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
      .ico {
        display: inline-flex;
        width: 24px;
        justify-content: center;
      }
      .done ha-svg-icon {
        color: var(--success-color);
      }
      .failed ha-svg-icon {
        color: var(--error-color);
      }
      .warning ha-svg-icon {
        color: var(--warning-color);
      }
      .pending ha-svg-icon,
      .skipped ha-svg-icon {
        color: var(--disabled-text-color);
      }
      .pending [slot="headline"],
      .skipped [slot="headline"] {
        color: var(--secondary-text-color);
      }
      .detail {
        white-space: pre-wrap;
        overflow-wrap: anywhere;
      }
      .failed .detail {
        color: var(--error-color);
      }
    `,
  ];
}

define("sep-step-list", SeStepList);

declare global {
  interface HTMLElementTagNameMap {
    "sep-step-list": SeStepList;
  }
}
