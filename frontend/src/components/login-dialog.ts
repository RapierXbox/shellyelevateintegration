import { LitElement, css, html, nothing } from "lit";
import { ElevateApi, type HaLoginUser, errorMessage } from "../api";
import { type HaFormSchema, type ValueChangedEvent, onDialogClosed } from "../ha";
import { dialogStyles, sharedStyles } from "../styles";
import { define, toast } from "../ui";

/** Select value of the dedicated user (the select cannot hold null). */
const DEDICATED = "_dedicated";

/**
 * The user the dashboards of all displays log in as. A display can still pick its own user in
 * its options. Call `show()`; fires `saved` after a change.
 */
export class SeLoginDialog extends LitElement {
  static properties = {
    api: { attribute: false },
    _open: { state: true },
    _users: { state: true },
    _user: { state: true },
    _busy: { state: true },
    _error: { state: true },
  };

  declare api: ElevateApi;
  declare _open: boolean;
  declare _users: HaLoginUser[];
  declare _user: string;
  declare _busy: boolean;
  declare _error: string;
  private _initial = DEDICATED;

  constructor() {
    super();
    this._open = false;
    this._users = [];
    this._user = DEDICATED;
    this._busy = false;
    this._error = "";
  }

  async show(): Promise<void> {
    this._error = "";
    this._busy = true;
    this._open = true;
    try {
      const config = await this.api.haLoginConfig();
      this._users = config.users;
      this._initial = config.default_user_id ?? DEDICATED;
      this._user = this._initial;
    } catch (err) {
      this._error = errorMessage(err);
    } finally {
      this._busy = false;
    }
  }

  private _closed = onDialogClosed(() => (this._open = false));

  private async _save(): Promise<void> {
    this._busy = true;
    this._error = "";
    try {
      await this.api.haLoginSetDefault(this._user === DEDICATED ? null : this._user);
      toast(this, "The displays log in as the new user", "success");
      this._open = false;
      this.dispatchEvent(new CustomEvent("saved"));
    } catch (err) {
      this._error = errorMessage(err);
    } finally {
      this._busy = false;
    }
  }

  private get _selected(): HaLoginUser | undefined {
    return this._users.find((u) => u.id === this._user);
  }

  render() {
    const others = this._users.filter((u) => !u.dedicated);
    const schema: HaFormSchema[] = [
      {
        name: "user",
        required: true,
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: DEDICATED, label: "Shelly Elevate (recommended)" },
              ...others.map((u) => ({ value: u.id, label: `${u.name}${u.admin ? " (administrator)" : ""}` })),
            ],
          },
        },
      },
    ];
    const selected = this._selected;
    return html`
      <ha-dialog .open=${this._open} header-title="Dashboard login" @closed=${this._closed}>
        ${this._error ? html`<ha-alert alert-type="error" class="error-alert">${this._error}</ha-alert>` : nothing}
        <p class="secondary intro">
          Home Assistant logs the dashboard of every display in by itself, so nobody types a password on a display. Each
          display gets its own login, which you can see and revoke under the user's profile.
        </p>
        <ha-form
          .hass=${this.api?.hass}
          .data=${{ user: this._user }}
          .schema=${schema}
          .disabled=${this._busy}
          .computeLabel=${() => "Log the displays in as"}
          @value-changed=${(e: ValueChangedEvent<{ user?: string }>) => {
            e.stopPropagation();
            this._user = e.detail.value.user ?? DEDICATED;
          }}
        ></ha-form>
        ${this._user === DEDICATED
          ? html`<p class="secondary note">
              A user without administrator rights that can only log in from the local network and has no password.
              Home Assistant creates it when the first display logs in.
            </p>`
          : selected?.admin
            ? html`<ha-alert alert-type="warning">
                Anyone at a display could change your Home Assistant settings as this administrator.
              </ha-alert>`
            : nothing}
        <p class="secondary note">A display can log in as another user in its options.</p>
        <ha-dialog-footer slot="footer">
          <ha-button slot="secondaryAction" appearance="plain" @click=${() => (this._open = false)}>Cancel</ha-button>
          <ha-button
            slot="primaryAction"
            .loading=${this._busy}
            ?disabled=${this._busy || this._user === this._initial}
            @click=${this._save}
            >Save</ha-button
          >
        </ha-dialog-footer>
      </ha-dialog>
    `;
  }

  static styles = [
    sharedStyles,
    dialogStyles,
    css`
      .intro {
        margin-top: 0;
      }
      .note {
        margin-top: var(--ha-space-4);
        font-size: var(--ha-font-size-s);
      }
      .error-alert {
        margin-bottom: var(--ha-space-4);
      }
    `,
  ];
}

define("sep-login-dialog", SeLoginDialog);

declare global {
  interface HTMLElementTagNameMap {
    "sep-login-dialog": SeLoginDialog;
  }
}
