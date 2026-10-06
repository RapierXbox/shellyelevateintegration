import { css } from "lit";

/**
 * Shared styles: a copy of the parts of Home Assistant's `haStyle` the panel uses, plus the
 * page / card rules of the config pages it mirrors (Settings → System → Backups:
 * `ha-config-backup-overview`, `ha-config-backup-settings`, `ha-backup-overview-backups`).
 * Card header / content / actions spacing comes from `ha-card` itself (its `::slotted` rules).
 */
export const sharedStyles = css`
  :host {
    font-family: var(--ha-font-family-body);
    -webkit-font-smoothing: var(--ha-font-smoothing);
    -moz-osx-font-smoothing: var(--ha-moz-osx-font-smoothing);
    font-size: var(--ha-font-size-m);
    font-weight: var(--ha-font-weight-normal);
    line-height: var(--ha-line-height-normal);
  }

  h1 {
    font-family: var(--ha-font-family-heading);
    -webkit-font-smoothing: var(--ha-font-smoothing);
    -moz-osx-font-smoothing: var(--ha-moz-osx-font-smoothing);
    font-size: var(--ha-font-size-2xl);
    font-weight: var(--ha-font-weight-normal);
    line-height: var(--ha-line-height-condensed);
  }

  a {
    color: var(--primary-color);
  }

  .secondary {
    color: var(--secondary-text-color);
  }

  .error {
    color: var(--error-color);
  }

  /* --- config page layout (ha-config-backup-overview) --- */
  .content {
    padding: 28px 20px 0;
    max-width: 690px;
    margin: 0 auto;
    gap: var(--ha-space-6);
    display: flex;
    flex-direction: column;
    margin-bottom: calc(72px + var(--safe-area-inset-bottom, 0px));
  }

  /* --- cards (ha-config-backup-settings / assist-pref) --- */
  p {
    color: var(--secondary-text-color);
  }
  .card-header {
    padding-bottom: 8px;
  }
  /* card content that ends with list rows (they bring their own padding) */
  .card-content.list {
    padding-bottom: 0;
  }
  .card-actions {
    display: flex;
    justify-content: flex-end;
  }
  /* icon buttons next to a card header (assist-pref) */
  .header-actions {
    position: absolute;
    right: 0px;
    inset-inline-end: 0px;
    inset-inline-start: initial;
    top: 24px;
    display: flex;
    flex-direction: row;
  }
  .header-actions > * {
    margin-top: -16px;
    margin-right: 8px;
    margin-inline-end: 8px;
    margin-inline-start: initial;
    color: var(--secondary-text-color);
  }

  /* --- lists in cards (ha-backup-overview-backups / ha-backup-config-schedule) --- */
  ha-list-item-button::part(start),
  ha-list-item-base::part(start) {
    color: var(--ha-color-text-secondary, var(--secondary-text-color));
  }
  /* A "⋮" button at the end of a list row: its 48px target overlaps the row padding so the row
     keeps the height of stock rows with a 24px end icon (ha-backup-overview-backups: 66px). */
  ha-list-item-button > ha-dropdown[slot="end"] > ha-icon-button,
  ha-list-item-base > ha-dropdown[slot="end"] > ha-icon-button {
    margin-block: calc(var(--ha-space-3) * -1);
  }
  ha-list-base.rows {
    --ha-row-item-padding-inline: 0;
  }
  ha-list-base.rows ha-list-item-base::part(headline),
  ha-list-base.rows ha-list-item-base::part(supporting-text) {
    white-space: wrap;
  }
  ha-dropdown {
    font-size: var(--ha-font-size-m);
    font-family: var(--ha-font-family-body);
    letter-spacing: normal;
  }

  ha-alert,
  ha-input,
  ha-select,
  ha-input-search {
    display: block;
  }

  .hidden {
    display: none !important;
  }

  .loading {
    display: flex;
    justify-content: center;
    padding: var(--ha-space-4);
  }

  /* Native textarea fallback when ha-code-editor is unavailable */
  textarea.fallback {
    box-sizing: border-box;
    width: 100%;
    min-height: 280px;
    font-family: var(--ha-font-family-code);
    font-size: var(--ha-font-size-s);
    color: var(--primary-text-color);
    background: var(--secondary-background-color);
    border: 1px solid var(--divider-color);
    border-radius: var(--ha-border-radius-md);
    padding: var(--ha-space-2);
  }
`;

/** Styles for content rendered inside `ha-dialog` (dialog-box / dialog-generate-backup). */
export const dialogStyles = css`
  /* stock dialogs (dialog-box, dialog-generate-backup) have no haStyle: normal line height */
  ha-dialog {
    line-height: normal;
  }
  .dialog-text {
    margin: 0 0 var(--ha-space-4);
    color: var(--primary-text-color);
  }
  .dialog-text.secondary {
    color: var(--secondary-text-color);
  }
  .stack {
    display: flex;
    flex-direction: column;
    gap: var(--ha-space-4);
  }
`;
