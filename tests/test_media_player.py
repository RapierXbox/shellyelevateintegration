"""Media player."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_EXTRA,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MP_DOMAIN,
    MediaPlayerEntityFeature,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, STATE_IDLE, STATE_PLAYING
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shellyelevateintegration.media_player import LEGACY_FEATURES

from .common import FakeDisplay, entity_id
from .conftest import setup_entry
from .const import LEGACY_DEVICE_ID


async def _call(hass: HomeAssistant, service: str, player: str, **data: Any) -> None:
    await hass.services.async_call(MP_DOMAIN, service, {ATTR_ENTITY_ID: player, **data}, blocking=True)


async def test_media_status(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """The display pushes its playback status."""
    player = entity_id(hass, MP_DOMAIN, "media_player")
    assert hass.states.get(player).state == STATE_IDLE
    display.client.push(
        {
            "type": "media_status",
            "status": {
                "state": "playing",
                "url": "http://radio/stream.mp3",
                "title": "Song",
                "artist": "Band",
                "album": "Album",
                "artwork": "http://radio/cover.jpg",
                "position": 12.5,
                "duration": 180.0,
                "volume": 0.4,
                "muted": False,
                "repeat": "all",
            },
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get(player)
    assert state.state == STATE_PLAYING
    assert state.attributes[ATTR_MEDIA_TITLE] == "Song"
    assert state.attributes["media_artist"] == "Band"
    assert state.attributes["media_album_name"] == "Album"
    assert state.attributes["media_duration"] == 180
    assert state.attributes["media_position"] == 12
    assert state.attributes["media_position_updated_at"] is not None
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.4
    assert state.attributes[ATTR_MEDIA_REPEAT] == "all"
    assert state.attributes["entity_picture"]

    display.client.push({"type": "media_status", "status": {"state": "weird", "repeat": "shuffle"}})
    await hass.async_block_till_done()
    state = hass.states.get(player)
    assert state.state == STATE_IDLE
    assert state.attributes.get(ATTR_MEDIA_REPEAT) == "off"
    assert "media_position_updated_at" not in state.attributes

    # a media error is only logged
    display.client.push({"type": "event", "event": "media_error", "url": "http://bad", "what": 1, "extra": -1004})
    display.client.push({"type": "settings_changed", "changes": {"screenSaverDelay": 60}})
    await hass.async_block_till_done()


async def test_controls(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """Every control is a media command."""
    player = entity_id(hass, MP_DOMAIN, "media_player")
    await _call(hass, "media_pause", player)
    await _call(hass, "media_play", player)
    await _call(hass, "media_stop", player)
    await _call(hass, "media_next_track", player)
    await _call(hass, "media_seek", player, **{ATTR_MEDIA_SEEK_POSITION: 30})
    await _call(hass, "volume_set", player, **{ATTR_MEDIA_VOLUME_LEVEL: 0.12345})
    await _call(hass, "volume_mute", player, **{ATTR_MEDIA_VOLUME_MUTED: True})
    await _call(hass, "repeat_set", player, **{ATTR_MEDIA_REPEAT: "one"})
    assert display.commands == [
        ("media.pause", {}),
        ("media.resume", {}),
        ("media.stop", {}),
        ("media.next", {}),
        ("media.seek", {"position": 30}),
        ("media.volume", {"volume": 0.123}),
        ("media.volume", {"muted": True}),
        ("media.repeat", {"mode": "one"}),
    ]


async def test_play_media(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """URLs, queueing, announcements and media sources."""
    player = entity_id(hass, MP_DOMAIN, "media_player")
    await _call(
        hass,
        "play_media",
        player,
        **{
            ATTR_MEDIA_CONTENT_ID: "http://radio/stream.mp3",
            ATTR_MEDIA_CONTENT_TYPE: "music",
            ATTR_MEDIA_ENQUEUE: "add",
            ATTR_MEDIA_EXTRA: {"title": "Radio", "artist": "DJ", "thumb": "http://radio/cover.jpg"},
        },
    )
    assert display.commands[-1] == (
        "media.play",
        {
            "url": "http://radio/stream.mp3",
            "channel": "music",
            "title": "Radio",
            "artist": "DJ",
            "artwork": "http://radio/cover.jpg",
            "enqueue": "add",
        },
    )
    await _call(
        hass,
        "play_media",
        player,
        **{
            ATTR_MEDIA_CONTENT_ID: "http://tts/hello.mp3",
            ATTR_MEDIA_CONTENT_TYPE: "music",
            ATTR_MEDIA_ANNOUNCE: True,
        },
    )
    assert display.commands[-1] == ("media.play", {"url": "http://tts/hello.mp3", "channel": "announce", "title": None})

    resolved = SimpleNamespace(url="http://homeassistant.local:8123/media/local/song.mp3", title="Local song")
    with patch(
        "custom_components.shellyelevateintegration.media_player.media_source.async_resolve_media",
        AsyncMock(return_value=resolved),
    ):
        await _call(
            hass,
            "play_media",
            player,
            **{ATTR_MEDIA_CONTENT_ID: "media-source://media_source/local/song.mp3", ATTR_MEDIA_CONTENT_TYPE: "music"},
        )
    assert display.commands[-1] == (
        "media.play",
        {"url": "http://homeassistant.local:8123/media/local/song.mp3", "channel": "music", "title": "Local song"},
    )


async def test_browse_media(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """Browsing shows audio media sources only."""
    player = entity_id(hass, MP_DOMAIN, "media_player")
    browse = AsyncMock(return_value="browsed")
    with patch("custom_components.shellyelevateintegration.media_player.media_source.async_browse_media", browse):
        entity = hass.data["entity_components"][MP_DOMAIN].get_entity(player)
        assert await entity.async_browse_media() == "browsed"
    content_filter = browse.await_args.kwargs["content_filter"]
    assert content_filter(SimpleNamespace(media_content_type="audio/mpeg"))
    assert not content_filter(SimpleNamespace(media_content_type="video/mp4"))


async def test_media_disabled(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> None:
    """Without media playback switched on there is no media player."""
    display.settings["mediaEnabled"] = False
    await setup_entry(hass, mock_config_entry)
    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id(MP_DOMAIN, "shellyelevateintegration", "shellyelevate-4a2f_media_player") is None
    )


async def test_media_without_speaker(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """A display without a speaker has no media player."""
    display.info["capabilities"]["speaker"] = False
    await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.runtime_data.media_active is False


@pytest.mark.usefixtures("init_legacy")
async def test_legacy_media_player(hass: HomeAssistant, legacy_display: FakeDisplay) -> None:
    """The legacy app plays media without readback of mute or repeat."""
    player = entity_id(hass, MP_DOMAIN, "media_player", LEGACY_DEVICE_ID)
    state = hass.states.get(player)
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == LEGACY_FEATURES
    assert not state.attributes[ATTR_SUPPORTED_FEATURES] & MediaPlayerEntityFeature.VOLUME_MUTE
    await _call(
        hass,
        "play_media",
        player,
        **{ATTR_MEDIA_CONTENT_ID: "http://radio/a.mp3", ATTR_MEDIA_CONTENT_TYPE: "music", ATTR_MEDIA_ENQUEUE: "add"},
    )
    assert legacy_display.commands[-1] == (
        "media.play",
        {"url": "http://radio/a.mp3", "channel": "music", "title": None},
    )
    assert ATTR_MEDIA_VOLUME_MUTED not in hass.states.get(player).attributes
    assert ATTR_MEDIA_REPEAT not in hass.states.get(player).attributes
    legacy_display.client.push({"type": "settings_changed", "changes": {"mediaEnabled": False}})
    await hass.async_block_till_done()
    assert hass.states.get(player).state == "unavailable"
