"""Assist satellite: the display's microphone and speaker as a voice assistant.

Flow (protocol v1):
  display --voice.wake--> HA; mic audio arrives on WS channel 0x01
  HA runs the pipeline, tells the display to stop streaming (voice.stop_audio),
  drives its voice UI (voice.state) and plays the TTS (voice.play_tts)
  display --voice.tts_finished--> HA

With speaker recognition the display marks voice.wake with speaker_pending and sends who said the
wake word as voice.speaker. The pipeline waits a moment for it so the conversation agent is told who
speaks. Audio keeps queuing meanwhile so nothing is lost.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components import assist_satellite
from homeassistant.components.assist_pipeline import (  # type: ignore[attr-defined]  # .models is 2026.10+
    PipelineEvent,
    PipelineEventType,
    PipelineStage,
)
from homeassistant.components.assist_satellite.entity import AssistSatelliteState
from homeassistant.components.intent import TimerEventType, TimerInfo, async_register_timer_handler
from homeassistant.components.media_player.browse_media import async_process_play_media_url
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import CHANNEL_AUDIO, ShellyElevateIntegrationError
from .const import DOMAIN
from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .entity import ShellyElevateIntegrationEntity, ShellyElevateIntegrationEntityDescription
from .voice import pipeline_select_entity_id, vad_select_entity_id

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
ANNOUNCE_TIMEOUT = 300
AUDIO_QUEUE_SIZE = 256
# the error code HA uses when another satellite already answered the same wake word
DUPLICATE_WAKE_UP = "duplicate_wake_up_detected"
# most seconds the pipeline waits for the speaker of the wake word. the user keeps talking meanwhile
SPEAKER_WAIT = 3.0
# on top of the last embedding time for loading the model and a busy display
SPEAKER_SLACK = 1.0
SPEAKER_KNOWN = "The person speaking is {name}."
# always sent: the chat log would otherwise keep the previous speaker for the next turns
SPEAKER_UNKNOWN = "The person speaking could not be identified."


@dataclass(frozen=True, kw_only=True)
class ShellyElevateIntegrationSatelliteDescription(
    ShellyElevateIntegrationEntityDescription, assist_satellite.AssistSatelliteEntityDescription
):
    """Satellite description."""


STATE_TO_DEVICE: dict[str, str] = {
    AssistSatelliteState.IDLE: "idle",
    AssistSatelliteState.LISTENING: "listening",
    AssistSatelliteState.PROCESSING: "processing",
    AssistSatelliteState.RESPONDING: "responding",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the satellite."""
    async_add_entities(create_entities(entry.runtime_data))


def create_entities(device: ShellyElevateIntegrationDevice) -> list[assist_satellite.AssistSatelliteEntity]:
    """The satellite while voice is switched on on the display."""
    return [ShellyElevateIntegrationAssistSatellite(device)] if device.voice_active else []


class ShellyElevateIntegrationAssistSatellite(ShellyElevateIntegrationEntity, assist_satellite.AssistSatelliteEntity):
    """The display as an Assist satellite."""

    entity_description: ShellyElevateIntegrationSatelliteDescription

    _attr_name = None
    _attr_supported_features = (
        assist_satellite.AssistSatelliteEntityFeature.ANNOUNCE
        | assist_satellite.AssistSatelliteEntityFeature.START_CONVERSATION
    )

    def __init__(self, device: ShellyElevateIntegrationDevice) -> None:
        """Initialize."""
        super().__init__(
            device, ShellyElevateIntegrationSatelliteDescription(key="assist_satellite", state_keys=("voice.state",))
        )
        self._audio_queue: asyncio.Queue[bytes | None] | None = None
        self._tts_done: asyncio.Event | None = None
        self._config = assist_satellite.AssistSatelliteConfiguration(
            available_wake_words=[], active_wake_words=[], max_active_wake_words=1
        )
        self._last_device_state: str | None = None
        # display session of the running wake word pipeline and its speaker result
        self._session: int | None = None
        self._speaker: asyncio.Future[dict[str, Any]] | None = None
        # bumped by every wake word so a pipeline still waiting for its speaker knows it was replaced
        self._generation = 0

    # ---------------------------------------------------------------- HA wiring

    @property
    def pipeline_entity_id(self) -> str | None:
        """Pipeline select of this display."""
        return pipeline_select_entity_id(self.hass, self.device)

    @property
    def vad_sensitivity_entity_id(self) -> str | None:
        """VAD select of this display."""
        return vad_select_entity_id(self.hass, self.device)

    @property
    def available(self) -> bool:
        """Unavailable while voice is switched off on the display."""
        if not super().available:
            return False
        if self.device.settings.get("haVoiceEnabled") is False:
            return False
        return self.device.state.get("voice.state") != "disabled"

    async def async_added_to_hass(self) -> None:
        """Subscribe to voice messages, audio and timers."""
        await super().async_added_to_hass()
        self.async_on_remove(self.device.async_add_message_listener(self._on_message))
        self.async_on_remove(self.device.async_add_availability_listener(self._on_availability))
        # the display sent its wake words when it connected, before this entity listened
        if (cached := self.device.client.voice_config) is not None:
            self._apply_config(cached)
        self.async_on_remove(self.device.client.subscribe_binary(CHANNEL_AUDIO, self._on_audio))
        assert self.registry_entry is not None
        if self.registry_entry.device_id:
            self.async_on_remove(async_register_timer_handler(self.hass, self.registry_entry.device_id, self._on_timer))

    async def async_will_remove_from_hass(self) -> None:
        """Stop a running pipeline."""
        self._end_audio()
        await super().async_will_remove_from_hass()

    # ---------------------------------------------------------------- configuration

    @callback
    def async_get_configuration(self) -> assist_satellite.AssistSatelliteConfiguration:
        """Wake words reported by the display."""
        return self._config

    async def async_set_configuration(self, config: assist_satellite.AssistSatelliteConfiguration) -> None:
        """Activate wake words on the display."""
        await self.device.async_command("voice.set_config", active=list(config.active_wake_words))
        self._config.active_wake_words = list(config.active_wake_words)

    # ---------------------------------------------------------------- display -> HA

    @callback
    def _on_message(self, message: dict[str, Any]) -> None:
        msg_type = message.get("type")
        if msg_type == "voice.wake":
            self._start_pipeline(
                wake_word_phrase=message.get("phrase"),
                session=message.get("session"),
                speaker_pending=bool(message.get("speaker_pending")),
            )
        elif msg_type == "voice.speaker":
            if self._speaker is not None and not self._speaker.done() and message.get("session") == self._session:
                self._speaker.set_result(message)

        elif msg_type == "voice.audio_end":
            self._end_audio()
        elif msg_type == "voice.tts_finished":
            if self._tts_done is not None:
                self._tts_done.set()
            self.tts_response_finished()
        elif msg_type == "voice.config":
            self._apply_config(message)
        elif msg_type == "settings_changed" and "haVoiceEnabled" in (message.get("changes") or {}):
            if not self.available:
                self._end_audio()
            self.async_write_ha_state()

    @callback
    def _handle_state(self, changes: dict[str, Any]) -> None:
        if "voice.state" in changes and not self.available:
            self._end_audio()
        super()._handle_state(changes)

    @callback
    def _on_availability(self) -> None:
        if not self.device.available:
            # a pipeline waiting for audio would otherwise hang until it times out
            self._end_audio()

    @callback
    def _apply_config(self, message: dict[str, Any]) -> None:
        """Wake words from a `voice.config` message."""
        self._config = assist_satellite.AssistSatelliteConfiguration(
            available_wake_words=[
                assist_satellite.AssistSatelliteWakeWord(
                    id=ww["id"], wake_word=ww.get("phrase", ww["id"]), trained_languages=ww.get("languages", [])
                )
                for ww in message.get("available", [])
            ],
            active_wake_words=list(message.get("active", [])),
            max_active_wake_words=int(message.get("max_active", 1)),
        )

    @callback
    def _on_audio(self, payload: bytes) -> None:
        if self._audio_queue is None:
            return
        try:
            self._audio_queue.put_nowait(payload)
        except asyncio.QueueFull:
            _LOGGER.debug("Audio queue full, dropping chunk")

    @callback
    def _start_pipeline(
        self, *, wake_word_phrase: str | None = None, session: int | None = None, speaker_pending: bool = False
    ) -> None:
        self._end_audio()
        queue: asyncio.Queue[bytes | None] = asyncio.Queue(AUDIO_QUEUE_SIZE)
        self._audio_queue = queue
        self._session = session
        self._generation += 1
        generation = self._generation
        speaker_active = self.device.speaker_active
        self._speaker = speaker = self.hass.loop.create_future() if speaker_active and speaker_pending else None

        async def _stream() -> AsyncIterator[bytes]:
            while (chunk := await queue.get()) is not None:
                yield chunk

        async def _run() -> None:
            try:
                if speaker_active:
                    wake: dict[str, Any] | None = None
                    if speaker is not None:
                        try:
                            async with asyncio.timeout(self._speaker_wait()):
                                wake = await speaker
                        except TimeoutError:
                            _LOGGER.debug("No speaker from %s in time", self.device.entry.title)
                    if self._generation != generation:
                        # a newer wake word took over while this one waited
                        return
                    self._add_speaker_prompt(wake)
                await self.async_accept_pipeline_from_satellite(
                    _stream(), start_stage=PipelineStage.STT, wake_word_phrase=wake_word_phrase
                )
            except Exception as err:
                _LOGGER.warning("Voice pipeline of %s failed: %s", self.device.entry.title, err)
                if self._audio_queue is queue:
                    self._end_audio()
                self._send("voice.stop_audio")
                self._send("voice.state", state="error", message=str(err))

        self.device.entry.async_create_background_task(self.hass, _run(), f"{DOMAIN} pipeline {self.device.device_id}")

    def _speaker_wait(self) -> float:
        """How long the display needed for the last wake word, within SPEAKER_WAIT."""
        latency = self.device.state.get("speaker.latency_ms")
        if not isinstance(latency, int | float) or latency <= 0:
            return SPEAKER_WAIT
        return min(SPEAKER_WAIT, latency / 1000 + SPEAKER_SLACK)

    def _add_speaker_prompt(self, wake: dict[str, Any] | None) -> None:
        """Tell the conversation agent who speaks next to any prompt start_conversation set."""
        if wake is not None and wake.get("status") == "identified" and wake.get("name"):
            line = SPEAKER_KNOWN.format(name=wake["name"])
            if person := wake.get("person"):
                line += f" Their Home Assistant person is {person}."
        else:
            line = SPEAKER_UNKNOWN
        prompt = self._extra_system_prompt
        self._extra_system_prompt = f"{prompt}\n{line}" if prompt else line

    @callback
    def _end_audio(self) -> None:
        if self._audio_queue is not None:
            try:
                self._audio_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
            self._audio_queue = None

    # ---------------------------------------------------------------- HA -> display

    def _send(self, action: str, **params: Any) -> None:
        async def _run() -> None:
            try:
                await self.device.client.command(action, **params)
            except ShellyElevateIntegrationError as err:
                _LOGGER.debug("Voice command %s failed: %s", action, err)

        self.hass.async_create_task(_run(), eager_start=True)

    @callback
    def on_pipeline_event(self, event: PipelineEvent) -> None:
        """Forward pipeline progress to the display."""
        data = event.data or {}
        if event.type in (PipelineEventType.STT_VAD_END, PipelineEventType.STT_END):
            self._end_audio()
            self._send("voice.stop_audio")
            text = (data.get("stt_output") or {}).get("text")
            if event.type is PipelineEventType.STT_END and text and self._session is not None and self.device.speaker_active:
                # recent voices in the panel show what was said
                self._send("speaker.recent.label", session=self._session, text=text)
        elif event.type is PipelineEventType.TTS_END:
            url = (data.get("tts_output") or {}).get("url")
            if url:
                self._send("voice.play_tts", url=async_process_play_media_url(self.hass, url))
        elif event.type is PipelineEventType.ERROR:
            self._end_audio()
            self._send("voice.stop_audio")
            if data.get("code") == DUPLICATE_WAKE_UP:
                # another satellite in the room answers this wake word, so this one just goes quiet
                self._send("voice.state", state="idle")
            else:
                self._send("voice.state", state="error", message=data.get("message"))
        elif event.type is PipelineEventType.RUN_END:
            self._end_audio()
        if event.type is PipelineEventType.RUN_START:
            # the display already listens since it sent voice.wake, the entity stays idle until stt-start.
            # a sync now sends idle when the entity is new (first wake after a restart) and ends the capture
            return
        self._sync_device_state()

    @callback
    def _sync_device_state(self) -> None:
        state = STATE_TO_DEVICE.get(self.state or "")
        if state is not None and state != self._last_device_state:
            self._last_device_state = state
            self._send("voice.state", state=state)

    @callback
    def tts_response_finished(self) -> None:
        """TTS done: back to idle."""
        super().tts_response_finished()
        self._sync_device_state()

    async def async_announce(self, announcement: assist_satellite.AssistSatelliteAnnouncement) -> None:
        """Play an announcement and wait until it finished."""
        await self._async_play_and_wait(announcement)

    async def async_start_conversation(self, start_announcement: assist_satellite.AssistSatelliteAnnouncement) -> None:
        """Announce, then listen without wake word."""
        await self._async_play_and_wait(start_announcement)
        self._start_pipeline()
        try:
            await self.device.async_command("voice.start", start_conversation=True)
        except HomeAssistantError:
            self._end_audio()
            raise

    async def _async_play_and_wait(self, announcement: assist_satellite.AssistSatelliteAnnouncement) -> None:
        params: dict[str, Any] = {"url": async_process_play_media_url(self.hass, announcement.media_id)}
        if announcement.preannounce_media_id:
            params["preannounce_url"] = async_process_play_media_url(self.hass, announcement.preannounce_media_id)
        self._tts_done = done = asyncio.Event()
        try:
            await self.device.async_command("voice.play_tts", **params)
            async with asyncio.timeout(ANNOUNCE_TIMEOUT):
                await done.wait()
        except TimeoutError as err:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="announce_timeout") from err
        finally:
            self._tts_done = None

    # ---------------------------------------------------------------- timers

    @callback
    def _on_timer(self, event_type: TimerEventType, timer: TimerInfo) -> None:
        self._send(
            "timer.update",
            event=str(event_type),
            timer={
                "id": timer.id,
                # the app shows a json null as "null"
                "name": timer.name or "",
                "total": timer.seconds,
                "remaining": timer.seconds_left,
                "active": timer.is_active,
            },
        )
