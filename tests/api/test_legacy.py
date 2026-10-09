"""Legacy client against a local legacy app (plain HTTP, polling)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import aiohttp
import pytest

from custom_components.shellyelevateintegration.api import (
    LegacyClient,
    ShellyElevateIntegrationAuthError,
    ShellyElevateIntegrationCommandError,
    ShellyElevateIntegrationConnectionError,
    ShellyElevateIntegrationUnsupportedError,
)
from custom_components.shellyelevateintegration.api.legacy import _float, _int, _reading

from ..const import DEVICE_ID, OTHER_DEVICE_ID
from .server import AppServer, silent_server

HOST = "127.0.0.1"
LEGACY = "custom_components.shellyelevateintegration.api.legacy"


@pytest.fixture
async def make_client(session: aiohttp.ClientSession, app_server: AppServer) -> AsyncGenerator[Any]:
    """Create legacy clients for the app; they stop polling after the test."""
    clients: list[LegacyClient] = []

    def factory(device_id: str | None = None) -> LegacyClient:
        client = LegacyClient(session, HOST, app_server.plain_port, device_id)
        clients.append(client)
        return client

    yield factory
    for client in clients:
        await client.disconnect()


async def _until(condition: Any, timeout: float = 3) -> None:
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0.01)


async def test_connect(make_client: Any, legacy_server: AppServer) -> None:
    """The model decides the capabilities; the first poll reads everything."""
    messages: list[dict[str, Any]] = []
    client = make_client()
    client.subscribe_events(messages.append)
    info = await client.connect()
    assert info.legacy is True
    assert info.device_id == "shellywalldisplay-legacy"
    assert info.model == "SAWD-2A1XX10EU1"
    assert info.fw_version == "2.4.1"
    caps = info.capabilities
    assert (caps.relays, caps.inputs, caps.optional_relays_from, caps.proximity) == (2, 1, 1, True)
    assert caps.temperature is True and caps.humidity is False and caps.lux is False
    assert caps.dimmer is True
    assert client.connected
    state = client.state
    assert state["relay.0"] is True and state["relay.1"] is False
    assert state["input.0"] is False
    assert state["temperature"] == 21.5
    assert "humidity" not in state and "lux" not in state
    assert state["proximity"] == 0.2 and state["presence"] is True
    assert (state["dimmer.on"], state["dimmer.brightness"], state["dimmer.power"]) == (True, 40, 3.5)
    assert state["screen.on"] is True
    assert state["screen.brightness"] == 180
    assert state["screen.auto_brightness"] is True
    assert state["webview.url"] == "http://homeassistant.local:8123/"
    assert client.media.volume == 0.6
    assert [m["type"] for m in messages] == ["media_status"]
    schema = await client.get_settings_schema()
    assert any(item.key == "liteMode" for item in schema)


async def test_connect_unknown_model(make_client: Any, legacy_server: AppServer) -> None:
    """Unknown hardware is treated like the original Wall Display, without a SKU."""
    legacy_server.legacy_root = {"modelName": "NEWTHING", "proximity": "false", "numOfInputs": "x"}
    legacy_server.legacy_values["/device/input?num=0"] = 500
    legacy_server.legacy_values["/device/getProximity"] = {"distance": -999}
    del legacy_server.legacy_values["/device/dimmer"]
    info = await make_client("given-id").connect()
    assert info.device_id == "given-id"
    assert info.model is None
    assert info.codename == "NEWTHING"
    assert info.name == "Shelly Wall Display"
    assert (info.capabilities.relays, info.capabilities.inputs, info.capabilities.proximity) == (1, 1, False)


async def test_connect_fails(make_client: Any, legacy_server: AppServer) -> None:
    """A display that does not answer, or answers garbage."""
    legacy_server.legacy_down = True
    with pytest.raises(ShellyElevateIntegrationCommandError):
        await make_client().connect()
    server, port = await silent_server()
    server.close()
    await server.wait_closed()
    client = LegacyClient(aiohttp.ClientSession(), HOST, port)
    try:
        with pytest.raises(ShellyElevateIntegrationConnectionError):
            await client.connect()
    finally:
        await client._session.close()


async def test_connect_detects_upgrade(make_client: Any, app_server: AppServer) -> None:
    """The app was updated to protocol v1 (and the legacy API switched off): pair again."""
    messages: list[dict[str, Any]] = []
    client = make_client(DEVICE_ID)
    client.subscribe_events(messages.append)
    with pytest.raises(ShellyElevateIntegrationAuthError):
        await client.connect()
    assert client.upgrade_available
    assert messages == [{"type": "_upgrade_available"}]
    # checked only once
    assert await client._check_upgrade() is True


async def test_upgrade_of_another_display(make_client: Any, app_server: AppServer) -> None:
    """A v1 display with another id at the address is no upgrade."""
    client = make_client(OTHER_DEVICE_ID)
    with pytest.raises(ShellyElevateIntegrationCommandError):
        await client.connect()
    assert not client.upgrade_available


async def test_poll_loop(make_client: Any, legacy_server: AppServer) -> None:
    """Polling marks the display unavailable after failures and finds a new app version."""
    changes: list[bool] = []
    messages: list[dict[str, Any]] = []
    with (
        patch(f"{LEGACY}.FAST_INTERVAL", 0.01),
        patch(f"{LEGACY}.SLOW_INTERVAL", 0.05),
    ):
        client = make_client()
        client.subscribe_connection(changes.append)
        client.subscribe_events(messages.append)
        await client.connect()
        legacy_server.legacy_root["version"] = "2.5.0"
        legacy_server.legacy_settings["screenSaverDelay"] = 90
        await _until(lambda: client.info.fw_version == "2.5.0")
        await _until(lambda: {"type": "settings_changed", "changes": {"screenSaverDelay": 90}} in messages)
        assert {"type": "_info_changed"} in messages

        legacy_server.legacy_down = True
        await _until(lambda: not client.connected)
        legacy_server.legacy_down = False
        await _until(lambda: client.connected)
        assert changes[-2:] == [False, True]

        # anything the app sends must not stop the loop
        real_poll = client._poll
        failures = 0

        async def flaky(*, slow: bool) -> None:
            nonlocal failures
            if failures < 2:
                failures += 1
                raise ValueError("garbage")
            await real_poll(slow=slow)

        with patch.object(client, "_poll", flaky):
            await _until(lambda: failures == 2)
            await asyncio.sleep(0.05)
        assert client.connected


async def test_settings(make_client: Any, legacy_server: AppServer) -> None:
    """Writes are reported by the client itself."""
    messages: list[dict[str, Any]] = []
    client = make_client()
    client.subscribe_events(messages.append)
    write = await client.set_settings({"screenSaverDelay": 60})
    assert write.applied == {"screenSaverDelay": 60}
    assert client.settings["liteMode"] is False
    assert messages[-1] == {"type": "settings_changed", "changes": {"screenSaverDelay": 60}}

    legacy_server.legacy_settings_echo = False
    write = await client.set_settings({"brightness": 10})
    assert write.settings["brightness"] == 10

    legacy_server.legacy_settings = "broken"  # type: ignore[assignment]
    with pytest.raises(ShellyElevateIntegrationCommandError, match="no settings"):
        await client.get_settings()


async def test_commands(make_client: Any, legacy_server: AppServer) -> None:
    """v1 commands map onto the legacy endpoints."""
    client = make_client()
    await client.connect()
    posts = legacy_server.legacy_posts
    await client.command("relay.set", index=1, on=True)
    assert posts[-1] == ("/device/relay", {"num": 1, "state": True})
    assert client.state["relay.1"] is True
    await client.command("dimmer.set", on=False, brightness=30)
    assert posts[-2:] == [("/device/dimmer", {"brightness": 30}), ("/device/dimmer", {"on": False})]
    await client.command("screen.sleep")
    assert client.state["screen.on"] is False
    await client.command("screen.wake")
    assert client.state["screen.on"] is True
    await client.command("screen.set", brightness=99)
    assert posts[-1] == ("/settings", {"brightness": 99, "automaticBrightness": False})
    assert client.state["screen.brightness"] == 99
    await client.command("screen.set", auto=True)
    assert posts[-1] == ("/settings", {"automaticBrightness": True})
    count = len(posts)
    await client.command("screen.set")
    assert len(posts) == count
    await client.command("night_mode.set", on=True)
    assert client.state["night_mode"] is True
    await client.command("webview.reload")
    assert posts[-1] == ("/webview/refresh", None)
    await client.command("webview.navigate", path="/lovelace/1")
    assert "http://homeassistant.local:8123/lovelace/1" in posts[-1][1]["javascript"]
    await client.command("webview.navigate", url="http://other/")
    with pytest.raises(ShellyElevateIntegrationCommandError):
        await client.command("webview.navigate")
    await client.command("ui.notify", message="Hi", title="Door", duration=2)
    assert '"Door\\nHi"' in posts[-1][1]["javascript"]
    assert "2000" in posts[-1][1]["javascript"]
    await client.command("device.reboot")
    assert posts[-1] == ("/device/reboot", None)


async def test_media_commands(make_client: Any, legacy_server: AppServer) -> None:
    """Media is tracked optimistically."""
    client = make_client()
    assert await client.command("media.play", url="http://a.mp3", title="A") == {}
    assert legacy_server.legacy_posts[-1] == ("/media/play", {"url": "http://a.mp3", "music": True, "volume": 0.5})
    assert client.media.state == "playing"
    assert client.media.title == "A"
    await client.command("media.play", url="http://tts.mp3", channel="announce", volume=0.9, enqueue="add")
    assert client.media.url == "http://a.mp3"
    await client.command("media.pause")
    assert client.media.state == "paused"
    await client.command("media.resume")
    assert client.media.state == "playing"
    await client.command("media.volume", volume=0.3)
    assert client.media.volume == 0.3
    await client.command("media.volume")
    await client.command("media.play", url="http://b.mp3")
    assert legacy_server.legacy_posts[-1][1]["volume"] == 0.3
    await client.command("media.stop")
    assert client.media.state == "idle"
    assert client.media.url is None
    with pytest.raises(ShellyElevateIntegrationUnsupportedError):
        await client.command("media.volume", muted=True)
    with pytest.raises(ShellyElevateIntegrationUnsupportedError):
        await client.command("voice.start")


async def test_http_errors(make_client: Any, legacy_server: AppServer) -> None:
    """Error statuses and non-JSON answers."""
    client = make_client()
    legacy_server.legacy_values["/device/night_mode"] = 500
    assert await client._get("/device/night_mode") is None
    with pytest.raises(ShellyElevateIntegrationCommandError, match="no sensor"):
        await client._call("GET", "/device/night_mode")
    assert await client._call("GET", "/plain-text") == {}


def test_value_helpers() -> None:
    """Readings and numbers from the legacy app."""
    assert _int("12") == 12
    assert _int(None, 3) == 3
    assert _float("x") is None
    assert _reading(-999) is None
    assert _reading("21.5") == 21.5
    assert _reading(None) is None
