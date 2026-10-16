import { LitElement, type PropertyValues, css, html, nothing } from "lit";
import { mdiAccountPlus, mdiAccountVoice, mdiContentCopy, mdiDelete, mdiDotsVertical, mdiMicrophone, mdiPencil } from "@mdi/js";
import {
  type DeviceSummary,
  ElevateApi,
  type RecentVoice,
  type Speaker,
  type SpeakerList,
  type SpeakerMessage,
  errorMessage,
  isLoaded,
} from "../api";
import {
  type DropdownSelectEvent,
  type HaFormSchema,
  type UnsubscribeFunc,
  type ValueChangedEvent,
  isChecked,
  onDialogClosed,
} from "../ha";
import { type PageContext, displayPicker, listCardStyles, noDisplaysCard, pageStyles, renderPage } from "../page";
import { dialogStyles, sharedStyles } from "../styles";
import { confirmDialog, define, plural, selectEntry, stopPropagation, toast, toastError } from "../ui";

const REASONS: Record<string, string> = {
  no_speech: "Nothing was heard. Speak a bit louder.",
  too_short: "That was too short.",
  too_loud: "Too loud. Step back a little.",
  different_voice: "That sounded like a different voice.",
};

/** add: name and record; record: more samples of a speaker; edit: name and person; claim: a recent voice */
type DialogMode = "add" | "record" | "edit" | "claim";

interface DialogState {
  mode: DialogMode;
  speakerId?: string;
  session?: number;
  name: string;
  person: string;
  everywhere: boolean;
  phase: "form" | "recording" | "done" | "failed";
  step: number;
  total: number;
  prompt: string;
  reason: string;
}

/** Voices of the household: who is enrolled on which display, enrollment and recent voices. */
export class SeSpeakersTab extends LitElement {
  static properties = {
    page: { attribute: false },
    api: { attribute: false },
    devices: { attribute: false },
    entryId: {},
    narrow: { type: Boolean, reflect: true },
    _lists: { state: true },
    _recent: { state: true },
    _loading: { state: true },
    _error: { state: true },
    _dialog: { state: true },
    _dialogOpen: { state: true },
    _busy: { state: true },
  };

  declare page: PageContext;
  declare api: ElevateApi;
  declare devices: DeviceSummary[];
  declare entryId: string;
  declare narrow: boolean;
  /** speaker.list of every loaded display by entry id */
  declare _lists: Record<string, SpeakerList>;
  declare _recent: RecentVoice[];
  declare _loading: boolean;
  declare _error: string;
  declare _dialog: DialogState | null;
  declare _dialogOpen: boolean;
  declare _busy: boolean;

  private _subscribedTo = "";
  private _unsub?: Promise<UnsubscribeFunc>;

  constructor() {
    super();
    this.devices = [];
    this.entryId = "";
    this.narrow = false;
    this._lists = {};
    this._recent = [];
    this._loading = false;
    this._error = "";
    this._dialog = null;
    this._dialogOpen = false;
    this._busy = false;
  }

  protected willUpdate(changed: PropertyValues<this>): void {
    if ((changed.has("entryId") || changed.has("api")) && this.api && this.entryId && this.entryId !== this._subscribedTo) {
      this._subscribe();
      this._load();
    }
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._unsub?.then((unsub) => unsub()).catch(() => undefined);
    this._unsub = undefined;
    this._subscribedTo = "";
  }

  private get _online(): DeviceSummary[] {
    return this.devices.filter((d) => isLoaded(d) && d.available && d.capabilities?.voice);
  }

  private get _list(): SpeakerList | undefined {
    return this._lists[this.entryId];
  }

  private _subscribe(): void {
    this._unsub?.then((unsub) => unsub()).catch(() => undefined);
    this._subscribedTo = this.entryId;
    this._unsub = this.api.subscribeSpeakers(this.entryId, (msg) => this._onMessage(msg));
    this._unsub.catch(() => undefined);
  }

  private async _load(): Promise<void> {
    const ids = this._online.map((d) => d.entry_id);
    this._loading = true;
    this._error = "";
    try {
      const results = ids.length ? await this.api.command(ids, "speaker.list") : {};
      const lists: Record<string, SpeakerList> = {};
      for (const [id, result] of Object.entries(results)) if (result.ok) lists[id] = result.data as SpeakerList;
      this._lists = lists;
      this._recent = lists[this.entryId]?.enabled
        ? (await this.api.speakerCommand<{ recent: RecentVoice[] }>(this.entryId, "speaker.recent")).recent.reverse()
        : [];
    } catch (err) {
      this._error = errorMessage(err);
    } finally {
      this._loading = false;
    }
  }

  /** Entry ids of the displays that have this speaker. */
  private _holders(speakerId: string): string[] {
    return Object.entries(this._lists)
      .filter(([, list]) => list.speakers.some((s) => s.id === speakerId))
      .map(([id]) => id);
  }

  private _name(entryId: string): string {
    return this.devices.find((d) => d.entry_id === entryId)?.name ?? entryId;
  }

  private _speakerName(id: string | null): string {
    for (const list of Object.values(this._lists)) {
      const speaker = list.speakers.find((s) => s.id === id);
      if (speaker) return speaker.name;
    }
    return "Unknown";
  }

  // ------------------------------------------------------------------ live messages

  private _onMessage(msg: SpeakerMessage): void {
    const dialog = this._dialog;
    if (msg.type === "event") {
      this._load();
      return;
    }
    if (msg.type !== "speaker.enroll" || !dialog || dialog.speakerId !== msg.speaker_id) return;
    const status = msg.status ?? "";
    if (status === "recording") {
      this._dialog = { ...dialog, step: msg.step ?? 0, total: msg.total ?? 0, prompt: msg.prompt ?? "", reason: msg.reason ?? "" };
    } else if (status === "done") {
      this._dialog = { ...dialog, phase: "done", step: dialog.total };
      this._finishRecording(dialog);
    } else {
      this._dialog = { ...dialog, phase: "failed", reason: status === "cancelled" ? "" : dialog.reason };
    }
  }

  private async _finishRecording(dialog: DialogState): Promise<void> {
    if (dialog.everywhere && dialog.speakerId) await this._copy(dialog.speakerId, true);
    await this._load();
  }

  // ------------------------------------------------------------------ actions

  private _open(mode: DialogMode, from: Partial<DialogState> = {}): void {
    this._dialog = {
      mode,
      name: "",
      person: "",
      everywhere: true,
      phase: "form",
      step: 0,
      total: 0,
      prompt: "",
      reason: "",
      ...from,
    };
    this._dialogOpen = true;
  }

  private async _submit(): Promise<void> {
    const dialog = this._dialog;
    if (!dialog) return;
    this._busy = true;
    try {
      const params = { name: dialog.name.trim(), person: dialog.person || null };
      if (dialog.mode === "edit") {
        await this.api.command(this._holders(dialog.speakerId!), "speaker.upsert", { id: dialog.speakerId, ...params });
        this._dialogOpen = false;
        await this._load();
        return;
      }
      if (dialog.mode === "claim") {
        const { id } = await this.api.speakerCommand<{ id: string }>(this.entryId, "speaker.upsert", params);
        await this.api.speakerCommand(this.entryId, "speaker.assign", { session: dialog.session, speaker_id: id });
        toast(this, `Saved as ${params.name}`, "success");
        this._dialogOpen = false;
        await this._load();
        return;
      }
      // a new speaker is created by the display when the recording starts
      const { speaker_id } = await this.api.speakerCommand<{ speaker_id: string }>(
        this.entryId,
        "speaker.enroll.start",
        dialog.speakerId ? { speaker_id: dialog.speakerId } : params,
      );
      this._dialog = { ...dialog, speakerId: speaker_id, phase: "recording" };
    } catch (err) {
      if (this._dialog) this._dialog = { ...this._dialog, phase: this._dialog.phase === "recording" ? "failed" : "form" };
      toastError(this, "Could not save the speaker", err);
    } finally {
      this._busy = false;
    }
  }

  private _closeDialog = onDialogClosed(() => {
    if (this._dialog?.phase === "recording") {
      this.api.speakerCommand(this.entryId, "speaker.enroll.cancel").catch(() => undefined);
    }
    this._dialogOpen = false;
    this._dialog = null;
  });

  /** Copies a speaker to the online displays that miss it (quiet: no toast on success). */
  private async _copy(speakerId: string, quiet = false): Promise<void> {
    const holders = [this.entryId, ...this._holders(speakerId)];
    const targets = this._online.map((d) => d.entry_id).filter((id) => !holders.includes(id));
    if (!targets.length) {
      if (!quiet) toast(this, "Every display already knows this voice");
      return;
    }
    try {
      const results = await this.api.speakersCopy(this.entryId, speakerId, targets);
      const failed = Object.entries(results).filter(([, r]) => !r.ok);
      if (failed.length) {
        toast(this, `Not copied to ${plural(failed.length, "display")}`, "warning", failed.map(([id, r]) => `${this._name(id)}: ${r.error}`));
      } else if (!quiet) {
        toast(this, `Copied to ${plural(targets.length, "display")}`, "success");
      }
      await this._load();
    } catch (err) {
      toastError(this, "Copy failed", err);
    }
  }

  private async _delete(speaker: Speaker): Promise<void> {
    const holders = this._holders(speaker.id);
    const ok = await confirmDialog(this, {
      title: `Forget ${speaker.name}?`,
      text: `The voice is removed from ${plural(holders.length, "display")}.`,
      confirmText: "Forget",
      destructive: true,
    });
    if (!ok) return;
    await this.api.command(holders, "speaker.delete", { id: speaker.id });
    await this._load();
  }

  private async _turnOn(): Promise<void> {
    try {
      await this.api.settingsSet(this.entryId, { speakerIdEnabled: true });
      toast(this, "Speaker recognition is on. The model downloads in the background.", "success");
      setTimeout(() => this._load(), 1500);
    } catch (err) {
      toastError(this, "Could not turn it on", err);
    }
  }

  private async _assign(voice: RecentVoice, value: string): Promise<void> {
    if (value === "new") {
      this._open("claim", { session: voice.session });
      return;
    }
    try {
      await this.api.speakerCommand(this.entryId, "speaker.assign", { session: voice.session, speaker_id: value });
      toast(this, `Learned from this voice: ${this._speakerName(value)}`, "success");
    } catch (err) {
      toastError(this, "Could not assign the voice", err);
    }
  }

  private _onSpeakerMenu(speaker: Speaker, ev: DropdownSelectEvent): void {
    switch (ev.detail.item.value) {
      case "record":
      case "edit":
        this._open(ev.detail.item.value, { speakerId: speaker.id, name: speaker.name, person: speaker.person ?? "" });
        break;
      case "copy":
        this._copy(speaker.id);
        break;
      case "delete":
        this._delete(speaker);
        break;
    }
  }

  // ------------------------------------------------------------------ render

  private _renderSpeakers(list: SpeakerList) {
    if (!list.speakers.length) {
      return html`<p>No voices yet. Add a speaker and say a few phrases at the display, or claim a recent voice below.</p>`;
    }
    return html`<ha-list-base aria-label="Speakers">
      ${list.speakers.map((s) => {
        const recorded = s.samples.filter((x) => x.audio).length;
        const holders = this._holders(s.id);
        return html`<ha-list-item-base>
          <ha-svg-icon slot="start" .path=${mdiAccountVoice}></ha-svg-icon>
          <span slot="headline">${s.name}</span>
          <span slot="supporting-text">
            ${s.person ? html`${this.page.hass.states?.[s.person]?.attributes.friendly_name ?? s.person} · ` : nothing}
            ${plural(recorded, "recording")}${s.samples.length > recorded ? ` + ${s.samples.length - recorded} learned` : ""} ·
            ${holders.length === this._online.length ? "all displays" : holders.map((id) => this._name(id)).join(", ")}
          </span>
          <ha-dropdown slot="end" placement="bottom-end" @click=${stopPropagation} @wa-select=${(e: DropdownSelectEvent) => this._onSpeakerMenu(s, e)}>
            <ha-icon-button slot="trigger" .label=${"Menu"} .path=${mdiDotsVertical}></ha-icon-button>
            <ha-dropdown-item value="record"><ha-svg-icon slot="icon" .path=${mdiMicrophone}></ha-svg-icon>Record more</ha-dropdown-item>
            <ha-dropdown-item value="edit"><ha-svg-icon slot="icon" .path=${mdiPencil}></ha-svg-icon>Name and person</ha-dropdown-item>
            <ha-dropdown-item value="copy" .disabled=${holders.length >= this._online.length}>
              <ha-svg-icon slot="icon" .path=${mdiContentCopy}></ha-svg-icon>Copy to all displays
            </ha-dropdown-item>
            <wa-divider></wa-divider>
            <ha-dropdown-item value="delete" variant="danger"><ha-svg-icon slot="icon" .path=${mdiDelete}></ha-svg-icon>Forget</ha-dropdown-item>
          </ha-dropdown>
        </ha-list-item-base>`;
      })}
    </ha-list-base>`;
  }

  private _renderRecent(list: SpeakerList) {
    return html`<ha-card>
      <div class="card-header">Recent voices</div>
      <div class="card-content list">
        <p class="intro">
          The last voice commands on this display. No audio is kept, so assigning a voice teaches the display what it
          sounded like until the model is changed.
        </p>
        ${this._recent.length
          ? html`<ha-list-base aria-label="Recent voices">
              ${this._recent.map(
                (v) => html`<ha-list-item-base>
                  <span slot="headline">${v.text ? `“${v.text}”` : "Voice command"}</span>
                  <span slot="supporting-text">
                    ${new Date(v.at).toLocaleTimeString(this.page.hass.locale?.language)} ·
                    ${v.status === "identified"
                      ? `${this._speakerName(v.best_guess)} (${Math.round(v.score * 100)} %)`
                      : v.best_guess
                        ? `unknown, closest ${this._speakerName(v.best_guess)} (${Math.round(v.score * 100)} %)`
                        : "unknown"}
                  </span>
                  <ha-dropdown slot="end" placement="bottom-end" @wa-select=${(e: DropdownSelectEvent) => this._assign(v, e.detail.item.value)}>
                    <ha-button slot="trigger" appearance="plain" size="small">This was…</ha-button>
                    ${list.speakers.map((s) => html`<ha-dropdown-item value=${s.id}>${s.name}</ha-dropdown-item>`)}
                    <ha-dropdown-item value="new"><ha-svg-icon slot="icon" .path=${mdiAccountPlus}></ha-svg-icon>New speaker…</ha-dropdown-item>
                  </ha-dropdown>
                </ha-list-item-base>`,
              )}
            </ha-list-base>`
          : html`<p>Nothing yet. Say the wake word at ${this._name(this.entryId)}.</p>`}
      </div>
    </ha-card>`;
  }

  private _renderContent() {
    if (!this.devices.some(isLoaded)) return noDisplaysCard(this, this.devices);
    const list = this._list;
    return html`
      ${this._error ? html`<ha-alert alert-type="error" title="Could not load the speakers">${this._error}</ha-alert>` : nothing}
      <ha-card>
        <div class="card-header">
          <span>Speakers</span>
          ${displayPicker(this.page.hass, this.devices, this.entryId, (entryId) => selectEntry(this, entryId))}
        </div>
        <div class="card-content list">
          ${!list
            ? this._loading
              ? html`<div class="loading"><ha-spinner></ha-spinner></div>`
              : html`<p>${this._name(this.entryId)} is offline or has no microphone.</p>`
            : !list.enabled
              ? html`<ha-alert alert-type="info" title="Speaker recognition is off on ${this._name(this.entryId)}">
                  Voice commands then tell Home Assistant who is speaking. It needs the voice assistant and about 20 MB.
                  <ha-button slot="action" appearance="plain" @click=${this._turnOn}>Turn on</ha-button>
                </ha-alert>`
              : this._renderSpeakers(list)}
        </div>
      </ha-card>
      ${list?.enabled ? this._renderRecent(list) : nothing}
    `;
  }

  private _renderDialog() {
    const d = this._dialog;
    if (!d) return nothing;
    const title = { add: "Add speaker", record: `Record ${d.name}`, edit: d.name, claim: "Who was this?" }[d.mode];
    const form = d.phase === "form";
    const schema: HaFormSchema[] = [
      { name: "name", required: true, selector: { text: {} } },
      { name: "person", selector: { entity: { filter: { domain: "person" } } } },
    ];
    const labels: Record<string, string> = { name: "Name", person: "Home Assistant person (optional)" };
    return html`<ha-dialog .open=${this._dialogOpen} header-title=${title} .preventScrimClose=${!form} @closed=${this._closeDialog}>
      ${form && d.mode !== "record"
        ? html`<ha-form
            .hass=${this.page.hass}
            .data=${{ name: d.name, person: d.person }}
            .schema=${schema}
            .disabled=${this._busy}
            .computeLabel=${(s: HaFormSchema) => labels[s.name] ?? s.name}
            @value-changed=${(e: ValueChangedEvent<{ name?: string; person?: string }>) => {
              e.stopPropagation();
              this._dialog = { ...d, name: e.detail.value.name ?? "", person: e.detail.value.person ?? "" };
            }}
          ></ha-form>`
        : nothing}
      ${form && (d.mode === "add" || d.mode === "record")
        ? html`<p class="dialog-text">
              Stand in front of <b>${this._name(this.entryId)}</b>. It shows six short phrases one after another; say each
              one when it appears. This takes about a minute.
            </p>
            <ha-checkbox .checked=${d.everywhere} @change=${(e: Event) => (this._dialog = { ...d, everywhere: isChecked(e) })}>
              Use this voice on all displays
            </ha-checkbox>`
        : nothing}
      ${d.phase === "recording"
        ? html`<div class="progress">
            <ha-spinner size="small"></ha-spinner>
            <div>
              <div>${d.total ? `Phrase ${d.step + 1} of ${d.total}` : "Starting…"}</div>
              ${d.prompt ? html`<div class="prompt">“${d.prompt}”</div>` : nothing}
              ${d.reason ? html`<div class="secondary">${REASONS[d.reason] ?? d.reason} Once more, please.</div>` : nothing}
            </div>
          </div>`
        : nothing}
      ${d.phase === "done" ? html`<ha-alert alert-type="success">${d.name}'s voice is saved.</ha-alert>` : nothing}
      ${d.phase === "failed"
        ? html`<ha-alert alert-type="warning">
            The recording stopped${d.reason ? `: ${REASONS[d.reason] ?? d.reason}` : ""}. The phrases that worked are kept.
          </ha-alert>`
        : nothing}
      <ha-dialog-footer slot="footer">
        ${form
          ? html`<ha-button slot="secondaryAction" appearance="plain" @click=${() => (this._dialogOpen = false)}>Cancel</ha-button>
              <ha-button slot="primaryAction" .loading=${this._busy} ?disabled=${this._busy || !d.name.trim()} @click=${this._submit}>
                ${d.mode === "add" || d.mode === "record" ? "Start recording" : "Save"}
              </ha-button>`
          : html`<ha-button slot="primaryAction" appearance=${d.phase === "recording" ? "plain" : "accent"} @click=${() => (this._dialogOpen = false)}>
              ${d.phase === "recording" ? "Stop" : "Done"}
            </ha-button>`}
      </ha-dialog-footer>
    </ha-dialog>`;
  }

  render() {
    if (!this.page) return nothing;
    const fab = this._list?.enabled
      ? html`<ha-button slot="fab" size="l" @click=${() => this._open("add")}>
          <ha-svg-icon slot="start" .path=${mdiAccountPlus}></ha-svg-icon>Add speaker
        </ha-button>`
      : nothing;
    return html`
      ${renderPage(this, this.page, html`<div class="content">${this._renderContent()}</div>`, fab, {
        onReload: () => {
          this._load();
        },
      })}
      ${this._renderDialog()}
    `;
  }

  static styles = [
    sharedStyles,
    pageStyles,
    listCardStyles,
    dialogStyles,
    css`
      .progress {
        display: flex;
        gap: var(--ha-space-4);
        align-items: center;
        margin: var(--ha-space-4) 0;
      }
      .prompt {
        font-size: var(--ha-font-size-xl);
        margin-top: var(--ha-space-1);
      }
    `,
  ];
}

define("sep-speakers-tab", SeSpeakersTab);

declare global {
  interface HTMLElementTagNameMap {
    "sep-speakers-tab": SeSpeakersTab;
  }
}
