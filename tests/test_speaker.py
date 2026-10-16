"""Speaker recognition: entities, the Assist prompt and the panel commands."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable
from typing import Any
from unittest.mock import patch

from homeassistant.components.assist_pipeline import PipelineEvent, PipelineEventType
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.shellyelevateintegration.api import CHANNEL_AUDIO
from custom_components.shellyelevateintegration.assist_satellite import (
    SPEAKER_UNKNOWN,
    ShellyElevateIntegrationAssistSatellite,
)
from custom_components.shellyelevateintegration.const import DOMAIN

from .common import FakeDisplay, entity_id
from .conftest import setup_entry
from .const import DEVICE_ID

SATELLITE = "custom_components.shellyelevateintegration.assist_satellite"
SPEAKER_STATE = {
    "speaker.state": "ready",
    "speaker.last": "Martin",
    "speaker.last_id": "id-martin",
    "speaker.person": "person.martin",
    "speaker.score": 0.734,
    "speaker.at": 1760000000000,
}
MARTIN = {"status": "identified", "speaker_id": "id-martin", "name": "Martin", "person": "person.martin"}


@pytest.fixture
async def speaker_display(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> FakeDisplay:
    """A voice display with speaker recognition switched on."""
    display.settings["speakerIdEnabled"] = True
    display.state |= SPEAKER_STATE
    await setup_entry(hass, mock_config_entry)
    return display


def _satellite(hass: HomeAssistant) -> ShellyElevateIntegrationAssistSatellite:
    return hass.data["entity_components"]["assist_satellite"].get_entity(
        entity_id(hass, "assist_satellite", "assist_satellite")
    )


class _Accept:
    """Stands in for the pipeline and records the speaker prompt it was started with."""

    def __init__(self) -> None:
        self.prompts: list[str | None] = []
        self.started = asyncio.Event()

        async def accept(satellite: Any, stream: AsyncIterable[bytes], **kwargs: Any) -> None:
            self.prompts.append(satellite._extra_system_prompt)
            satellite._extra_system_prompt = None
            self.started.set()
            async for _chunk in stream:
                pass

        self.fn = accept


async def test_entities(hass: HomeAssistant, speaker_display: FakeDisplay) -> None:
    """The sensors, the event and the switch follow the display."""
    state = hass.states.get(entity_id(hass, "sensor", "last_speaker"))
    assert state.state == "Martin"
    assert state.attributes["person"] == "person.martin"
    assert state.attributes["speaker_id"] == "id-martin"
    assert state.attributes["at"].startswith("2025-10-09")
    assert hass.states.get(entity_id(hass, "sensor", "speaker_confidence")).state == "73"
    assert hass.states.get(entity_id(hass, "switch", "speaker_recognition")).state == "on"

    speaker_display.client.push_state({"speaker.last": "unknown", "speaker.score": None, "speaker.at": None})
    await hass.async_block_till_done()
    state = hass.states.get(entity_id(hass, "sensor", "last_speaker"))
    assert state.state == "unknown"
    assert state.attributes["at"] is None
    assert hass.states.get(entity_id(hass, "sensor", "speaker_confidence")).state == "unknown"

    event = entity_id(hass, "event", "speaker")
    speaker_display.client.push({"type": "event", "event": "speaker", "session": 3, **MARTIN})
    await hass.async_block_till_done()
    assert hass.states.get(event).attributes["event_type"] == "identified"
    assert hass.states.get(event).attributes["name"] == "Martin"
    speaker_display.client.push({"type": "event", "event": "speaker", "status": "odd"})
    speaker_display.client.push({"type": "event", "event": "swipe", "direction": "up"})
    await hass.async_block_till_done()
    assert hass.states.get(event).attributes["event_type"] == "identified"


async def test_no_entities_while_off(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """Without speaker recognition there are no speaker entities and no prompt."""
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{DEVICE_ID}_last_speaker") is None
    assert registry.async_get_entity_id("event", DOMAIN, f"{DEVICE_ID}_speaker") is None


async def test_prompt_names_the_speaker(hass: HomeAssistant, speaker_display: FakeDisplay) -> None:
    """The pipeline waits for the wake word speaker and tells the agent who speaks."""
    accept = _Accept()
    with patch.object(ShellyElevateIntegrationAssistSatellite, "async_accept_pipeline_from_satellite", accept.fn):
        speaker_display.client.push({"type": "voice.wake", "session": 5, "speaker_pending": True})
        await asyncio.sleep(0)
        assert not accept.started.is_set()
        # another session's result does not count
        speaker_display.client.push({"type": "voice.speaker", "session": 4, "stage": "wake", **MARTIN})
        speaker_display.client.push({"type": "voice.speaker", "session": 5, "stage": "wake", **MARTIN})
        await accept.started.wait()
        speaker_display.client.push({"type": "voice.audio_end"})
        await hass.async_block_till_done()
    assert accept.prompts == [
        "The person speaking is Martin. Their Home Assistant person is person.martin."
    ]


async def test_prompt_is_appended(hass: HomeAssistant, speaker_display: FakeDisplay) -> None:
    """A prompt start_conversation set stays and an unknown speaker is said explicitly."""
    accept = _Accept()
    _satellite(hass)._extra_system_prompt = "Ask about dinner."
    with patch.object(ShellyElevateIntegrationAssistSatellite, "async_accept_pipeline_from_satellite", accept.fn):
        # a session the controller started has no wake word to recognise
        speaker_display.client.push({"type": "voice.wake", "session": 6})
        await accept.started.wait()
        speaker_display.client.push({"type": "voice.audio_end"})
        await hass.async_block_till_done()
    assert accept.prompts == [f"Ask about dinner.\n{SPEAKER_UNKNOWN}"]


async def test_wait_times_out(hass: HomeAssistant, speaker_display: FakeDisplay) -> None:
    """A display that never answers only delays the pipeline a moment."""
    accept = _Accept()
    with (
        patch(f"{SATELLITE}.SPEAKER_WAIT", 0.01),
        patch.object(ShellyElevateIntegrationAssistSatellite, "async_accept_pipeline_from_satellite", accept.fn),
    ):
        speaker_display.client.push({"type": "voice.wake", "session": 7, "speaker_pending": True})
        await accept.started.wait()
        speaker_display.client.push({"type": "voice.audio_end"})
        await hass.async_block_till_done()
    assert accept.prompts == [SPEAKER_UNKNOWN]


async def test_newer_wake_replaces_a_waiting_one(hass: HomeAssistant, speaker_display: FakeDisplay) -> None:
    """Only the newest wake word starts a pipeline."""
    accept = _Accept()
    with patch.object(ShellyElevateIntegrationAssistSatellite, "async_accept_pipeline_from_satellite", accept.fn):
        speaker_display.client.push({"type": "voice.wake", "session": 8, "speaker_pending": True})
        await asyncio.sleep(0)
        speaker_display.client.push({"type": "voice.wake", "session": 9, "speaker_pending": True})
        speaker_display.client.push({"type": "voice.speaker", "session": 8, "stage": "wake", **MARTIN})
        speaker_display.client.push({"type": "voice.speaker", "session": 9, "stage": "wake", "status": "unknown"})
        await accept.started.wait()
        speaker_display.client.push({"type": "voice.audio_end"})
        await hass.async_block_till_done()
    assert accept.prompts == [SPEAKER_UNKNOWN]


async def test_transcript_labels_the_session(hass: HomeAssistant, speaker_display: FakeDisplay) -> None:
    """The recognised text goes back to the display for its recent voices."""
    accept = _Accept()
    satellite = _satellite(hass)
    with patch.object(ShellyElevateIntegrationAssistSatellite, "async_accept_pipeline_from_satellite", accept.fn):
        speaker_display.client.push({"type": "voice.wake", "session": 11})
        await accept.started.wait()
        satellite.on_pipeline_event(
            PipelineEvent(PipelineEventType.STT_END, {"stt_output": {"text": "turn on the light"}})
        )
        await hass.async_block_till_done()
    assert ("speaker.recent.label", {"session": 11, "text": "turn on the light"}) in speaker_display.commands


async def test_ws_subscribe(
    hass: HomeAssistant, speaker_display: FakeDisplay, mock_config_entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Enrollment progress and recognised speakers reach the panel."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/speakers/subscribe", "entry_id": "nope"})
    assert (await client.receive_json())["error"]["code"] == "not_found"
    await client.send_json_auto_id({"type": f"{DOMAIN}/speakers/subscribe", "entry_id": mock_config_entry.entry_id})
    assert (await client.receive_json())["success"]

    speaker_display.client.push({"type": "event", "event": "swipe"})
    speaker_display.client.push({"type": "speaker.enroll", "step": 1, "total": 6, "status": "recording"})
    speaker_display.client.push({"type": "event", "event": "speaker", **MARTIN})
    first = await client.receive_json()
    second = await client.receive_json()
    assert first["event"]["type"] == "speaker.enroll"
    assert first["event"]["step"] == 1
    assert second["event"]["name"] == "Martin"


async def test_ws_copy(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    display: FakeDisplay,
    second_display: tuple[FakeDisplay, MockConfigEntry],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A speaker and its recorded samples go to other displays under the same id."""
    other, other_entry = second_display
    display.command_results["speaker.list"] = {
        "speakers": [
            {
                "id": "id-martin",
                "name": "Martin",
                "person": None,
                "samples": [
                    {"id": "s1", "kind": "wake", "audio": True},
                    {"id": "s2", "kind": "free", "audio": False},
                ],
            }
        ]
    }
    display.command_results["speaker.sample.get"] = {"pcm_b64": "AAAA"}
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/speakers/copy",
            "source": init_integration.entry_id,
            "speaker_id": "id-martin",
            "targets": [other_entry.entry_id, init_integration.entry_id, "nope"],
        }
    )
    result = (await client.receive_json())["result"]["results"]
    assert result[other_entry.entry_id] == {"ok": True}
    assert result["nope"]["ok"] is False
    assert ("speaker.sample.get", {"speaker_id": "id-martin", "sample_id": "s1"}) in display.commands
    assert other.commands == [
        ("speaker.upsert", {"id": "id-martin", "name": "Martin", "person": None}),
        ("speaker.sample.put", {"speaker_id": "id-martin", "sample_id": "s1", "kind": "wake", "pcm_b64": "AAAA"}),
    ]

    await client.send_json_auto_id(
        {
            "type": f"{DOMAIN}/speakers/copy",
            "source": init_integration.entry_id,
            "speaker_id": "someone",
            "targets": [other_entry.entry_id],
        }
    )
    assert (await client.receive_json())["error"]["message"].startswith("The speaker is not on the source display")


async def test_wait_follows_the_display(hass: HomeAssistant, speaker_display: FakeDisplay) -> None:
    """The wait is the display's last embedding time plus some slack, never more than the cap."""
    satellite = _satellite(hass)
    assert satellite._speaker_wait() == 3.0
    speaker_display.client.push_state({"speaker.latency_ms": 700})
    assert satellite._speaker_wait() == pytest.approx(1.7)
    speaker_display.client.push_state({"speaker.latency_ms": 9000})
    assert satellite._speaker_wait() == 3.0


async def test_audio_end_during_the_wait(hass: HomeAssistant, speaker_display: FakeDisplay) -> None:
    """A short command that ends before the speaker is known still runs with what was said."""
    accept = _Accept()
    received: list[bytes] = []

    async def collect(satellite: Any, stream: AsyncIterable[bytes], **kwargs: Any) -> None:
        accept.prompts.append(satellite._extra_system_prompt)
        satellite._extra_system_prompt = None
        async for chunk in stream:
            received.append(chunk)
        accept.started.set()

    with patch.object(ShellyElevateIntegrationAssistSatellite, "async_accept_pipeline_from_satellite", collect):
        speaker_display.client.push({"type": "voice.wake", "session": 21, "speaker_pending": True})
        await asyncio.sleep(0)
        speaker_display.client.push_binary(CHANNEL_AUDIO, b"\x01\x02")
        speaker_display.client.push({"type": "voice.audio_end"})
        speaker_display.client.push({"type": "voice.speaker", "session": 21, "stage": "wake", **MARTIN})
        await accept.started.wait()
    assert received == [b"\x01\x02"]
    assert accept.prompts[0].startswith("The person speaking is Martin.")


async def test_subscription_survives_a_reload(
    hass: HomeAssistant, speaker_display: FakeDisplay, mock_config_entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Turning speaker recognition on reloads the entry and the panel keeps getting progress."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": f"{DOMAIN}/speakers/subscribe", "entry_id": mock_config_entry.entry_id})
    assert (await client.receive_json())["success"]
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    speaker_display.clients[-1].push({"type": "speaker.enroll", "step": 2, "total": 6, "status": "recording"})
    assert (await client.receive_json())["event"]["step"] == 2
