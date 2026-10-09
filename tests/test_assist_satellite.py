"""Assist satellite and the voice selects."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from homeassistant.components.assist_pipeline import PipelineEvent, PipelineEventType
from homeassistant.components.assist_satellite import (
    AssistSatelliteAnnouncement,
    AssistSatelliteConfiguration,
)
from homeassistant.components.intent import TimerEventType
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shellyelevateintegration.api import (
    CHANNEL_AUDIO,
    ShellyElevateIntegrationCommandError,
)
from custom_components.shellyelevateintegration.assist_satellite import (
    ShellyElevateIntegrationAssistSatellite,
)

from .common import FakeDisplay, entity_id
from .conftest import setup_entry

SATELLITE = "custom_components.shellyelevateintegration.assist_satellite"
VOICE_CONFIG = {
    "type": "voice.config",
    "available": [
        {"id": "okay_nabu", "phrase": "Okay Nabu", "languages": ["en"]},
        {"id": "hey_jarvis"},
    ],
    "active": ["okay_nabu"],
    "max_active": 1,
}


def _satellite(hass: HomeAssistant) -> ShellyElevateIntegrationAssistSatellite:
    return hass.data["entity_components"]["assist_satellite"].get_entity(
        entity_id(hass, "assist_satellite", "assist_satellite")
    )


def _announcement(media_id: str = "http://ha.local:8123/api/tts_proxy/hello.mp3", **kwargs: Any):
    return AssistSatelliteAnnouncement(
        message="Hello", media_id=media_id, original_media_id=media_id, tts_token=None, media_id_source="url", **kwargs
    )


async def _settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


@pytest.fixture
async def voice_display(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> FakeDisplay:
    """A display with voice switched on that sent its wake words when it connected."""
    display.voice_config = VOICE_CONFIG
    await setup_entry(hass, mock_config_entry)
    return display


async def test_satellite_and_selects(hass: HomeAssistant, voice_display: FakeDisplay) -> None:
    """The satellite exists with the wake words of the display and its pipeline selects."""
    satellite = _satellite(hass)
    assert hass.states.get(satellite.entity_id).state == "idle"
    config = satellite.async_get_configuration()
    assert [ww.id for ww in config.available_wake_words] == ["okay_nabu", "hey_jarvis"]
    assert config.available_wake_words[1].wake_word == "hey_jarvis"
    assert config.active_wake_words == ["okay_nabu"]
    assert satellite.pipeline_entity_id is not None
    assert satellite.vad_sensitivity_entity_id is not None
    assert hass.states.get(satellite.pipeline_entity_id).state == "preferred"

    await satellite.async_set_configuration(
        AssistSatelliteConfiguration(available_wake_words=[], active_wake_words=["hey_jarvis"], max_active_wake_words=1)
    )
    assert voice_display.commands[-1] == ("voice.set_config", {"active": ["hey_jarvis"]})
    assert satellite.async_get_configuration().active_wake_words == ["hey_jarvis"]

    voice_display.client.push({**VOICE_CONFIG, "active": [], "max_active": 2})
    await hass.async_block_till_done()
    assert satellite.async_get_configuration().max_active_wake_words == 2

    # the selects follow the display
    voice_display.client.set_available(False)
    await hass.async_block_till_done()
    assert hass.states.get(satellite.pipeline_entity_id).state == STATE_UNAVAILABLE
    assert hass.states.get(satellite.entity_id).state == STATE_UNAVAILABLE


async def test_unavailable_while_voice_off(hass: HomeAssistant, voice_display: FakeDisplay) -> None:
    """Voice switched off on the display, or its voice state disabled, make it unavailable."""
    satellite = _satellite(hass)
    voice_display.client.push_state({"voice.state": "disabled"})
    await hass.async_block_till_done()
    assert hass.states.get(satellite.entity_id).state == STATE_UNAVAILABLE
    voice_display.client.push_state({"voice.state": "idle"})
    voice_display.client.push({"type": "settings_changed", "changes": {"haVoiceEnabled": False}})
    await hass.async_block_till_done()
    assert hass.states.get(satellite.entity_id).state == STATE_UNAVAILABLE


async def test_wake_runs_pipeline(hass: HomeAssistant, voice_display: FakeDisplay) -> None:
    """A wake word streams the microphone into the pipeline until the display ends it."""
    received: list[bytes] = []
    started = asyncio.Event()
    done = asyncio.Event()

    async def accept(self: Any, stream: AsyncIterable[bytes], **kwargs: Any) -> None:
        assert kwargs["wake_word_phrase"] == "Okay Nabu"
        started.set()
        async for chunk in stream:
            received.append(chunk)
        done.set()

    with patch.object(ShellyElevateIntegrationAssistSatellite, "async_accept_pipeline_from_satellite", accept):
        voice_display.client.push_binary(CHANNEL_AUDIO, b"ignored before the wake word")
        voice_display.client.push({"type": "voice.wake", "phrase": "Okay Nabu"})
        await started.wait()
        voice_display.client.push_binary(CHANNEL_AUDIO, b"\x01\x02")
        voice_display.client.push_binary(CHANNEL_AUDIO, b"\x03\x04")
        voice_display.client.push({"type": "voice.audio_end"})
        await done.wait()
    assert received == [b"\x01\x02", b"\x03\x04"]


async def test_pipeline_failure(hass: HomeAssistant, voice_display: FakeDisplay) -> None:
    """A failing pipeline stops the microphone and shows the error."""

    async def accept(self: Any, stream: AsyncIterable[bytes], **kwargs: Any) -> None:
        raise HomeAssistantError("no pipeline")

    voice_display.command_errors["voice.state"] = ShellyElevateIntegrationCommandError("busy")
    with patch.object(ShellyElevateIntegrationAssistSatellite, "async_accept_pipeline_from_satellite", accept):
        voice_display.client.push({"type": "voice.wake"})
        await hass.async_block_till_done()
        await _settle()
    actions = [action for action, _ in voice_display.commands]
    assert "voice.stop_audio" in actions
    assert ("voice.state", {"state": "error", "message": "no pipeline"}) in voice_display.commands


async def test_pipeline_events(hass: HomeAssistant, voice_display: FakeDisplay) -> None:
    """Pipeline progress drives the display."""
    satellite = _satellite(hass)
    with patch.object(ShellyElevateIntegrationAssistSatellite, "async_accept_pipeline_from_satellite"):
        satellite._start_pipeline()  # an audio stream is open
        await hass.async_block_till_done()
    for event in (
        PipelineEvent(PipelineEventType.RUN_START, {}),
        PipelineEvent(PipelineEventType.STT_VAD_END, None),
        PipelineEvent(PipelineEventType.TTS_END, {"tts_output": {"url": "http://ha.local:8123/api/tts_proxy/x.mp3"}}),
        PipelineEvent(PipelineEventType.TTS_END, {"tts_output": {}}),
        PipelineEvent(PipelineEventType.ERROR, {"code": "stt-no-text", "message": "No text"}),
        PipelineEvent(PipelineEventType.RUN_END, None),
    ):
        satellite.on_pipeline_event(event)
    await _settle()
    commands = voice_display.commands
    assert ("voice.stop_audio", {}) in commands
    assert ("voice.play_tts", {"url": "http://ha.local:8123/api/tts_proxy/x.mp3"}) in commands
    assert ("voice.state", {"state": "error", "message": "No text"}) in commands

    voice_display.client.push({"type": "voice.tts_finished"})
    await _settle()


async def test_announce(hass: HomeAssistant, voice_display: FakeDisplay) -> None:
    """An announcement plays on the display and finishes when the display says so."""
    satellite = _satellite(hass)
    task = hass.async_create_task(
        satellite.async_announce(_announcement(preannounce_media_id="http://ha.local:8123/static/chime.mp3"))
    )
    await _settle()
    assert voice_display.commands[-1] == (
        "voice.play_tts",
        {
            "url": "http://ha.local:8123/api/tts_proxy/hello.mp3",
            "preannounce_url": "http://ha.local:8123/static/chime.mp3",
        },
    )
    voice_display.client.push({"type": "voice.tts_finished"})
    await task


async def test_announce_timeout(hass: HomeAssistant, voice_display: FakeDisplay) -> None:
    """An announcement that never finishes fails."""
    with patch(f"{SATELLITE}.ANNOUNCE_TIMEOUT", 0.01), pytest.raises(HomeAssistantError) as err:
        await _satellite(hass).async_announce(_announcement())
    assert err.value.translation_key == "announce_timeout"


async def test_start_conversation(hass: HomeAssistant, voice_display: FakeDisplay) -> None:
    """Announce, then listen without a wake word."""
    satellite = _satellite(hass)
    with patch.object(ShellyElevateIntegrationAssistSatellite, "async_accept_pipeline_from_satellite"):
        task = hass.async_create_task(satellite.async_start_conversation(_announcement()))
        await _settle()
        voice_display.client.push({"type": "voice.tts_finished"})
        await task
        assert voice_display.commands[-1] == ("voice.start", {"start_conversation": True})

        voice_display.command_errors["voice.start"] = ShellyElevateIntegrationCommandError("busy")
        task = hass.async_create_task(satellite.async_start_conversation(_announcement()))
        await _settle()
        voice_display.client.push({"type": "voice.tts_finished"})
        with pytest.raises(HomeAssistantError):
            await task
        await hass.async_block_till_done()


async def test_timers(hass: HomeAssistant, voice_display: FakeDisplay) -> None:
    """Assist timers are shown on the display."""
    timer = SimpleNamespace(id="t1", name=None, seconds=300, seconds_left=299, is_active=True)
    _satellite(hass)._on_timer(TimerEventType.STARTED, timer)
    await _settle()
    assert voice_display.commands[-1] == (
        "timer.update",
        {"event": "started", "timer": {"id": "t1", "name": "", "total": 300, "remaining": 299, "active": True}},
    )


async def test_audio_ends_when_display_goes(hass: HomeAssistant, voice_display: FakeDisplay) -> None:
    """A pipeline waiting for audio is ended when the display goes away or turns voice off."""
    satellite = _satellite(hass)
    ended = asyncio.Event()

    async def accept(self: Any, stream: AsyncIterable[bytes], **kwargs: Any) -> None:
        async for _chunk in stream:
            pass
        ended.set()

    with patch.object(ShellyElevateIntegrationAssistSatellite, "async_accept_pipeline_from_satellite", accept):
        for trigger in (
            lambda: voice_display.client.set_available(False),
            lambda: voice_display.client.push_state({"voice.state": "disabled"}),
            lambda: voice_display.client.push({"type": "settings_changed", "changes": {"haVoiceEnabled": False}}),
        ):
            voice_display.client.set_available(True)
            voice_display.client.push_state({"voice.state": "idle"})
            voice_display.settings["haVoiceEnabled"] = True
            voice_display.client.settings["haVoiceEnabled"] = True
            ended.clear()
            satellite._start_pipeline()
            await _settle()
            trigger()
            await asyncio.wait_for(ended.wait(), 1)
        # a full queue drops chunks instead of blocking
        voice_display.client.set_available(True)
        satellite._audio_queue = asyncio.Queue(1)
        satellite._on_audio(b"a")
        satellite._on_audio(b"b")
        satellite._end_audio()
        await hass.async_block_till_done()


async def test_no_satellite_without_voice(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """Without voice switched on there is no satellite."""
    display.settings["haVoiceEnabled"] = False
    await setup_entry(hass, mock_config_entry)
    assert hass.states.async_entity_ids("assist_satellite") == []
