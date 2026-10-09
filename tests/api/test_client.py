"""Protocol v1 client against a local app (TLS with a pinned self-signed certificate)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import aiohttp
from homeassistant.core import HomeAssistant
import pytest

from custom_components.shellyelevateintegration.api import (
    CHANNEL_AUDIO,
    ShellyElevateIntegrationAuthError,
    ShellyElevateIntegrationCertificateError,
    ShellyElevateIntegrationClient,
    ShellyElevateIntegrationCommandError,
    ShellyElevateIntegrationConnectionError,
    ShellyElevateIntegrationIncompatibleError,
    ShellyElevateIntegrationPairingError,
    ShellyElevateIntegrationUnsupportedError,
    async_pair_confirm,
    async_pair_start,
    async_probe,
    client as client_module,
)
from custom_components.shellyelevateintegration.api.client import (
    _no_verify_context,
    _pinned,
    _ProbeTimeout,
    pairing_proof,
)

from ..const import DEVICE_ID, OTHER_DEVICE_ID
from .server import CODE, PAIRING_ID, TOKEN, AppServer, silent_server

HOST = "127.0.0.1"
CLIENT = "custom_components.shellyelevateintegration.api.client"


@pytest.fixture
def fast_reconnect() -> Any:
    """Reconnect at once."""
    with patch(f"{CLIENT}.RECONNECT_MIN", 0.01), patch(f"{CLIENT}.RECONNECT_MAX", 0.02):
        yield


@pytest.fixture
async def make_client(session: aiohttp.ClientSession, app_server: AppServer) -> AsyncGenerator[Any]:
    """Create clients for the app; they are disconnected after the test."""
    clients: list[ShellyElevateIntegrationClient] = []

    def factory(
        token: str = TOKEN, fingerprint: str | None = "", device_id: str | None = DEVICE_ID
    ) -> ShellyElevateIntegrationClient:
        client = ShellyElevateIntegrationClient(
            session,
            HOST,
            app_server.port,
            token,
            app_server.fingerprint if fingerprint == "" else fingerprint,
            device_id,
        )
        clients.append(client)
        return client

    yield factory
    for client in clients:
        await client.disconnect()


async def _until(condition: Any, timeout: float = 3) -> None:
    async with asyncio.timeout(timeout):
        while not condition():
            await asyncio.sleep(0.01)


# --------------------------------------------------------------------------- helpers


def test_pairing_proof_binds_certificate() -> None:
    """The proof depends on the code, the pairing and the certificate."""
    proof = pairing_proof(" 123456 ", "p", "ab" * 32)
    assert proof == pairing_proof("123456", "p", "ab" * 32)
    assert proof != pairing_proof("123456", "p", "cd" * 32)
    assert proof != pairing_proof("123457", "p", "ab" * 32)


def test_pinned_fingerprint() -> None:
    """A malformed or missing fingerprint pins nothing."""
    assert _pinned("ab" * 32) is not None
    assert _pinned("not hex") is None
    assert _pinned(None) is None
    assert _no_verify_context() is _no_verify_context()


# --------------------------------------------------------------------------- probe


async def test_probe_v1(session: aiohttp.ClientSession, app_server: AppServer) -> None:
    """The app answers its hello over TLS; the fingerprint is recorded."""
    with patch(f"{CLIENT}.DEFAULT_PORT", app_server.port):
        hello = await async_probe(session, HOST, app_server.port)
    assert hello.device_id == DEVICE_ID
    assert hello.legacy is False
    assert hello.port == app_server.port
    assert hello.paired is True
    assert hello.fingerprint == app_server.fingerprint
    assert hello.api_version == "1.0"


async def test_probe_compat_server(session: aiohttp.ClientSession, app_server: AppServer) -> None:
    """On the plain port an updated app names its TLS port."""
    with patch(f"{CLIENT}.DEFAULT_PORT", 1):
        hello = await async_probe(session, HOST, app_server.plain_port)
    assert hello.port == app_server.port
    assert hello.legacy is False


async def test_probe_legacy(session: aiohttp.ClientSession, legacy_server: AppServer) -> None:
    """The legacy app answers GET / and its settings carry its id."""
    hello = await async_probe(session, HOST, legacy_server.plain_port, plain_first=True)
    assert hello.legacy is True
    assert hello.device_id == "shellywalldisplay-legacy"
    assert hello.codename == "PEGASUS"
    assert hello.fw_version == "2.4.1"
    assert hello.port == legacy_server.plain_port

    del legacy_server.legacy_settings["mqttDeviceId"]
    hello = await async_probe(session, HOST, legacy_server.plain_port, plain_first=True)
    assert hello.device_id == "shellyelevate-127-0-0-1"


async def test_probe_default_port_last(session: aiohttp.ClientSession, app_server: AppServer) -> None:
    """With another port given, v1 on the default port is tried last."""
    app_server.compat_hint = False
    with patch(f"{CLIENT}.DEFAULT_PORT", app_server.port):
        hello = await async_probe(session, HOST, app_server.plain_port)
    assert hello.port == app_server.port


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"hello_status": 500}, "HTTP 500"),
        ({"hello_body": "<html>"}, "Cannot reach"),
        ({"hello_body": {"name": "no id"}}, "not a ShellyElevate display"),
    ],
)
async def test_probe_bad_hello(
    session: aiohttp.ClientSession, app_server: AppServer, change: dict[str, Any], message: str
) -> None:
    """Anything but a proper hello is not a display."""
    for key, value in change.items():
        setattr(app_server, key, value)
    app_server.compat_hint = False
    with (
        patch(f"{CLIENT}.DEFAULT_PORT", app_server.port),
        patch(f"{CLIENT}.LEGACY_PORT", app_server.plain_port),
        pytest.raises(ShellyElevateIntegrationConnectionError) as err,
    ):
        await async_probe(session, HOST, app_server.port)
    assert "not a ShellyElevate display" in str(err.value) or "Unexpected HTTP" in str(err.value)
    # the TLS attempt itself
    with pytest.raises(ShellyElevateIntegrationConnectionError, match=message):
        await client_module._probe_v1(session, HOST, app_server.port)


async def test_probe_plain_not_a_display(session: aiohttp.ClientSession, legacy_server: AppServer) -> None:
    """A web server without modelName is not a display."""
    legacy_server.legacy_root = {"something": "else"}
    with pytest.raises(ShellyElevateIntegrationConnectionError, match="not a ShellyElevate display"):
        await client_module._probe_plain(session, HOST, legacy_server.plain_port)


async def test_probe_nothing_listening(session: aiohttp.ClientSession) -> None:
    """A closed port is a connection error."""
    server, port = await silent_server()
    server.close()
    await server.wait_closed()
    with patch(f"{CLIENT}.DEFAULT_PORT", port), pytest.raises(ShellyElevateIntegrationConnectionError):
        await async_probe(session, HOST, port)


async def test_probe_timeout(session: aiohttp.ClientSession) -> None:
    """A host that never answers is not asked again on other ports."""
    server, port = await silent_server()
    try:
        with (
            patch(f"{CLIENT}.REQUEST_TIMEOUT", 0.3),
            patch(f"{CLIENT}.HANDSHAKE_TIMEOUT", 0.2),
        ):
            with pytest.raises(_ProbeTimeout):
                await async_probe(session, HOST, port, plain_first=True)
            with pytest.raises(ShellyElevateIntegrationConnectionError):
                await client_module._fetch_fingerprint(HOST, port)
    finally:
        server.close()
        await server.wait_closed()


async def test_probe_tls_timeout(session: aiohttp.ClientSession) -> None:
    """The whole TLS connect timing out is a timeout of the probe."""

    async def hang(*args: Any, **kwargs: Any) -> None:
        await asyncio.sleep(10)

    with (
        patch(f"{CLIENT}.asyncio.open_connection", hang),
        patch(f"{CLIENT}.REQUEST_TIMEOUT", 0.05),
        pytest.raises(_ProbeTimeout),
    ):
        await client_module._fetch_fingerprint(HOST, 1)


async def test_fingerprint_without_certificate() -> None:
    """A TLS server that presents no certificate is refused."""

    class Writer:
        def get_extra_info(self, name: str) -> None:
            return None

        def close(self) -> None:
            pass

    async def connect(*args: Any, **kwargs: Any) -> tuple[None, Writer]:
        return None, Writer()

    with (
        patch(f"{CLIENT}.asyncio.open_connection", connect),
        pytest.raises(ShellyElevateIntegrationConnectionError, match="no certificate"),
    ):
        await client_module._fetch_fingerprint(HOST, 1)


async def test_probe_v1_hello_timeout(session: aiohttp.ClientSession, app_server: AppServer) -> None:
    """A TLS server that does not answer the hello in time."""

    app_server.hello_delay = 0.5
    with patch(f"{CLIENT}.REQUEST_TIMEOUT", 0.2), pytest.raises(_ProbeTimeout):
        await client_module._probe_v1(session, HOST, app_server.port)


# --------------------------------------------------------------------------- pairing


async def test_pairing(session: aiohttp.ClientSession, app_server: AppServer) -> None:
    """The code proves the pairing for the pinned certificate."""
    fingerprint = app_server.fingerprint
    pairing_id = await async_pair_start(
        session, HOST, app_server.port, "client", "Home Assistant", fingerprint=fingerprint
    )
    assert pairing_id == PAIRING_ID
    token = await async_pair_confirm(session, HOST, app_server.port, pairing_id, CODE, fingerprint=fingerprint)
    assert token == TOKEN
    with pytest.raises(ShellyElevateIntegrationPairingError) as err:
        await async_pair_confirm(session, HOST, app_server.port, pairing_id, "000000", fingerprint=fingerprint)
    assert err.value.code == "invalid_code"


@pytest.mark.parametrize(
    ("status", "body", "error", "code"),
    [
        (429, {"error": "rate_limited"}, ShellyElevateIntegrationPairingError, "rate_limited"),
        (410, {}, ShellyElevateIntegrationPairingError, "invalid_code"),
        (500, {"error": "boom"}, ShellyElevateIntegrationConnectionError, None),
        (200, {"pairing_id": ""}, ShellyElevateIntegrationConnectionError, None),
    ],
)
async def test_pair_start_errors(
    session: aiohttp.ClientSession, app_server: AppServer, status: int, body: dict, error: type, code: str | None
) -> None:
    """Refusals and bad answers."""
    app_server.pair_status = status
    app_server.pair_body = body
    with pytest.raises(error) as err:
        await async_pair_start(session, HOST, app_server.port, "c", fingerprint=app_server.fingerprint)
    if code is not None:
        assert err.value.code == code


async def test_pair_certificate_errors(
    session: aiohttp.ClientSession, app_server: AppServer, impostor: AppServer
) -> None:
    """Another certificate or none at all: nothing is sent."""
    with pytest.raises(ShellyElevateIntegrationCertificateError):
        await async_pair_start(session, HOST, app_server.port, "c", fingerprint=impostor.fingerprint)
    with pytest.raises(ShellyElevateIntegrationCertificateError):
        await async_pair_start(session, HOST, app_server.port, "c", fingerprint="nonsense")
    server, port = await silent_server()
    server.close()
    await server.wait_closed()
    with pytest.raises(ShellyElevateIntegrationConnectionError):
        await async_pair_start(session, HOST, port, "c", fingerprint=app_server.fingerprint)


# --------------------------------------------------------------------------- client: HTTP


async def test_connect(make_client: Any, app_server: AppServer) -> None:
    """Connect reads info, state and settings and opens the WebSocket."""
    client = make_client()
    info = await client.connect()
    assert info.device_id == DEVICE_ID
    assert client.connected
    caps = client.capabilities
    assert caps.push and caps.media_status and caps.settings_schema
    assert caps.voice is True
    assert client.state["relay.1"] is True
    assert client.settings["screenSaverDelay"] == 45
    await _until(lambda: app_server.ws_connects == 1)


async def test_requests(make_client: Any, app_server: AppServer) -> None:
    """Settings, schema, commands over HTTP, screenshot, logs, token rotation and revoke."""
    client = make_client()
    write = await client.set_settings({"screenSaverDelay": 90, "unknown": 1})
    assert write.applied == {"screenSaverDelay": 90}
    assert write.ignored == ["unknown"]
    assert client.settings["screenSaverDelay"] == 90
    schema = await client.get_settings_schema()
    assert any(item.key == "screenSaverDelay" for item in schema)
    assert await client.command("screen.wake", source="test") == {"action": "screen.wake", "source": "test"}
    assert await client.screenshot() == b"\x89PNG-server"
    assert await client.get_logs(10) == "10 lines\n"
    assert await client.rotate_token() == "rotated-token"
    await client.revoke()
    assert ("DELETE", "/pair") in app_server.requests
    with pytest.raises(ShellyElevateIntegrationConnectionError):
        await client.send_binary(CHANNEL_AUDIO, b"x")


async def test_schema_items(make_client: Any, app_server: AppServer) -> None:
    """Invalid schema items are dropped; a schema without rules gets the app's rules."""
    app_server.schema = [
        {"key": "screenSaverDelay", "type": "int"},
        "garbage",
        {"type": "bool"},
        {"key": "screenSaver", "type": "bool"},
    ]
    schema = await make_client().get_settings_schema()
    assert [item.key for item in schema] == ["screenSaverDelay", "screenSaver"]
    assert schema[0].visible_if == [{"key": "screenSaver", "eq": True}]
    app_server.schema = {"not": "a list"}
    assert await make_client().get_settings_schema() == []


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        ({"error": "busy", "message": "try later"}, ShellyElevateIntegrationCommandError),
        ({"error": "unsupported", "message": "no dimmer"}, ShellyElevateIntegrationUnsupportedError),
    ],
)
async def test_http_command_errors(make_client: Any, app_server: AppServer, failure: dict, error: type) -> None:
    """Rejected commands raise with their error code."""
    app_server.fail_command = failure
    with pytest.raises(error):
        await make_client().command("dimmer.set", on=True)


async def test_http_errors(make_client: Any, app_server: AppServer, impostor: AppServer) -> None:
    """Rejected tokens, error pages, bad info and unpinned clients."""
    with pytest.raises(ShellyElevateIntegrationAuthError):
        await make_client(token="wrong").get_settings()
    app_server.html_error_on = {"/settings", "/screenshot"}
    with pytest.raises(ShellyElevateIntegrationCommandError, match="invalid JSON"):
        await make_client().get_settings()
    with pytest.raises(ShellyElevateIntegrationCommandError):
        await make_client().screenshot()
    with pytest.raises(ShellyElevateIntegrationCertificateError):
        await make_client(fingerprint=None).get_settings()
    with pytest.raises(ShellyElevateIntegrationCertificateError):
        await make_client(fingerprint=impostor.fingerprint).get_settings()

    app_server.info = ["not", "an", "object"]  # type: ignore[assignment]
    with pytest.raises(ShellyElevateIntegrationCommandError, match="not an object"):
        await make_client().get_info()
    app_server.info = {"name": "no id"}
    with pytest.raises(ShellyElevateIntegrationCommandError, match="bad info"):
        await make_client().get_info()


async def test_connect_errors(make_client: Any, app_server: AppServer, impostor: AppServer) -> None:
    """Another API version, an unreachable display, another certificate."""
    app_server.info["api"] = "2.0"
    with pytest.raises(ShellyElevateIntegrationIncompatibleError):
        await make_client().connect()
    app_server.info["api"] = "1.0"

    # the same display with a new key: pair again
    with pytest.raises(ShellyElevateIntegrationCertificateError):
        await make_client(fingerprint=impostor.fingerprint).connect()
    # another device took the address: not ours, retry later
    with pytest.raises(ShellyElevateIntegrationConnectionError, match="Another display"):
        await make_client(fingerprint=impostor.fingerprint, device_id=OTHER_DEVICE_ID).connect()
    # nothing answers the check either
    with (
        patch(f"{CLIENT}._probe_v1", side_effect=ShellyElevateIntegrationConnectionError("gone")),
        pytest.raises(ShellyElevateIntegrationConnectionError),
    ):
        await make_client(fingerprint=impostor.fingerprint).connect()


async def test_unreachable(session: aiohttp.ClientSession) -> None:
    """A closed port is a connection error."""
    server, port = await silent_server()
    server.close()
    await server.wait_closed()
    client = ShellyElevateIntegrationClient(session, HOST, port, TOKEN, "ab" * 32)
    with pytest.raises(ShellyElevateIntegrationConnectionError):
        await client.get_settings()


# --------------------------------------------------------------------------- client: WebSocket


async def test_websocket_messages(make_client: Any, app_server: AppServer) -> None:
    """State, events, results, binary frames and garbage over the WebSocket."""
    messages: list[dict[str, Any]] = []
    states: list[dict[str, Any]] = []
    audio: list[bytes] = []
    app_server.ws_greeting = [
        {"type": "state", "state": {"relay.0": True}},
        "not json",
        ["not", "an", "object"],
        b"",
        bytes([CHANNEL_AUDIO]) + b"pcm",
        {"type": "pong"},
        {"type": "result", "id": 999, "success": True},
        {"type": "hello", "info": {"name": "missing id"}},
        {"type": "event", "event": "swipe", "direction": "up"},
    ]
    client = make_client()
    client.subscribe_events(messages.append)
    client.subscribe_state(states.append)
    client.subscribe_binary(CHANNEL_AUDIO, audio.append)
    await client.connect()
    await _until(lambda: messages)
    assert messages == [{"type": "event", "event": "swipe", "direction": "up"}]
    assert {"relay.0": True} in states
    assert audio == [b"pcm"]

    await app_server.push({"type": "state_delta", "changes": {"relay.1": False}})
    await _until(lambda: client.state.get("relay.1") is False)
    assert client.state["relay.0"] is True

    assert await client.command("screen.wake") == {"action": "screen.wake"}
    app_server.fail_command = {"error": "unsupported"}
    with pytest.raises(ShellyElevateIntegrationUnsupportedError):
        await client.command("dimmer.set")
    app_server.fail_command = {"error": "busy", "message": "later"}
    with pytest.raises(ShellyElevateIntegrationCommandError):
        await client.command("dimmer.set")
    app_server.fail_command = None

    await client.send_binary(CHANNEL_AUDIO, b"tts")
    await _until(lambda: bytes([CHANNEL_AUDIO]) + b"tts" in app_server.ws_received)


async def test_websocket_command_timeout(make_client: Any, app_server: AppServer) -> None:
    """An unanswered command times out; pending commands fail when the connection drops."""
    app_server.ws_answer_commands = False
    client = make_client()
    await client.connect()
    await _until(lambda: app_server.websockets)
    await _until(lambda: client._ws is not None)
    with patch(f"{CLIENT}.COMMAND_TIMEOUT", 0.05), pytest.raises(ShellyElevateIntegrationConnectionError):
        await client.command("screen.wake")
    pending = asyncio.ensure_future(client.command("screen.sleep"))
    await _until(lambda: client._pending)
    await client.disconnect()
    with pytest.raises(ShellyElevateIntegrationConnectionError):
        await pending


async def test_websocket_send_fails(make_client: Any, app_server: AppServer) -> None:
    """A send on a broken socket is a connection error."""
    client = make_client()
    await client.connect()
    await _until(lambda: client._ws is not None)
    with (
        patch.object(client._ws, "send_json", side_effect=ConnectionResetError("reset")),
        pytest.raises(ShellyElevateIntegrationConnectionError),
    ):
        await client.command("screen.wake")


async def test_hello_and_settings_refresh(make_client: Any, app_server: AppServer) -> None:
    """A hello after a reconnect re-reads the settings; a new version or capabilities are reported."""
    messages: list[dict[str, Any]] = []
    client = make_client()
    client.subscribe_events(messages.append)
    await client.connect()
    await _until(lambda: app_server.websockets)
    app_server.settings["screenSaverDelay"] = 300
    new_info = {**app_server.info, "fw": "3.26160.0900"}
    await app_server.push({"type": "hello", "info": new_info})
    await _until(lambda: {"type": "settings_changed", "changes": {"screenSaverDelay": 300}} in messages)
    assert {"type": "_info_changed"} in messages
    assert client.info.fw_version == "3.26160.0900"

    # a reset to the default is read back instead of caching null
    messages.clear()
    app_server.settings["screenSaverDelay"] = 45
    await app_server.push({"type": "settings_changed", "changes": {"screenSaverDelay": None}})
    await _until(lambda: messages)
    assert messages == [{"type": "settings_changed", "changes": {"screenSaverDelay": 45}}]

    # nothing changed: nothing reported; a failed read is only logged
    messages.clear()
    await app_server.push({"type": "hello", "info": new_info})
    await asyncio.sleep(0.1)
    app_server.token = "other"
    await app_server.push({"type": "settings_changed", "changes": {"x": None}})
    await asyncio.sleep(0.1)
    assert messages == []
    app_server.token = TOKEN
    await app_server.push({"type": "settings_changed", "changes": {"touchToWake": False}})
    await _until(lambda: messages)
    assert client.settings["touchToWake"] is False


async def test_incompatible_hello(make_client: Any, app_server: AppServer) -> None:
    """A display that switched to another major version is not used anymore."""
    messages: list[dict[str, Any]] = []
    client = make_client()
    client.subscribe_events(messages.append)
    await client.connect()
    await _until(lambda: app_server.websockets)
    await app_server.push({"type": "hello", "info": {**app_server.info, "api": "2.0"}})
    await _until(lambda: messages)
    assert messages == [{"type": "_incompatible"}]
    assert not client.connected
    await app_server.push({"type": "event", "event": "swipe"})
    await asyncio.sleep(0.05)
    assert messages == [{"type": "_incompatible"}]


@pytest.mark.usefixtures("fast_reconnect")
async def test_reconnect(make_client: Any, app_server: AppServer) -> None:
    """A dropped WebSocket reconnects; a failed handshake is retried; a rejected token stops."""
    changes: list[bool] = []
    messages: list[dict[str, Any]] = []
    client = make_client()
    client.subscribe_connection(changes.append)
    client.subscribe_events(messages.append)
    app_server.ws_greeting = [{"type": "state", "state": {"relay.0": False}}]
    await client.connect()
    await _until(lambda: app_server.ws_connects == 1)

    app_server.ws_reject = 500
    with patch(f"{CLIENT}.RECONNECT_STABLE", 0):
        await app_server.close_websockets()
        await _until(lambda: False in changes)
    await asyncio.sleep(0.1)
    app_server.ws_reject = None
    await _until(lambda: app_server.ws_connects == 2)
    await _until(lambda: client.connected)

    app_server.ws_reject = 401
    await app_server.close_websockets()
    await _until(lambda: {"type": "_auth_failed"} in messages)
    await _until(lambda: client._ws_task.done())
    assert not client.connected


@pytest.mark.usefixtures("fast_reconnect")
@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_unexpected_websocket_error(make_client: Any, app_server: AppServer) -> None:
    """The push channel survives anything and reconnects."""
    client = make_client()
    original = client._ws_receive
    calls = 0

    async def flaky(ws: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("bug")
        await original(ws)

    with patch.object(client, "_ws_receive", flaky):
        await client.connect()
        await _until(lambda: app_server.ws_connects == 2)


@pytest.mark.usefixtures("fast_reconnect")
async def test_certificate_changes_while_connected(
    hass: HomeAssistant, make_client: Any, app_server: AppServer, tmp_path: Path
) -> None:
    """After a restart with another certificate: the same display asks to pair, another one is waited out."""
    messages: list[dict[str, Any]] = []
    client = make_client()
    client.subscribe_events(messages.append)
    await client.connect()
    await _until(lambda: app_server.ws_connects == 1)

    # another device answers on the address (its hello has another id)
    with (
        patch(f"{CLIENT}._probe_v1", side_effect=ShellyElevateIntegrationConnectionError("other")),
        patch.object(client._session, "ws_connect", side_effect=aiohttp.ServerFingerprintMismatch(b"a", b"b", HOST, 1)),
    ):
        await app_server.close_websockets()
        await asyncio.sleep(0.15)
    assert {"type": "_auth_failed"} not in messages

    # the display itself with a new key
    with patch.object(
        client._session, "ws_connect", side_effect=aiohttp.ServerFingerprintMismatch(b"a", b"b", HOST, 1)
    ):
        await _until(lambda: {"type": "_auth_failed"} in messages)
    assert not client.connected


async def test_websocket_timeout_error(make_client: Any, app_server: AppServer) -> None:
    """Connection errors of the WebSocket are retried quietly."""
    client = make_client()
    with (
        patch(f"{CLIENT}.RECONNECT_MIN", 0.01),
        patch.object(client._session, "ws_connect", side_effect=aiohttp.ClientConnectionError("refused")),
    ):
        await client.connect()
        await asyncio.sleep(0.05)
    assert app_server.ws_connects == 0


async def test_websocket_closed_while_closing(make_client: Any, app_server: AppServer) -> None:
    """A socket that ends while the client is closing is not reopened."""
    client = make_client()
    await client.connect()
    await _until(lambda: app_server.websockets)
    client._closing = True
    await app_server.close_websockets()
    await _until(lambda: client._ws_task.done())
    assert app_server.ws_connects == 1


async def test_websocket_error_frame(make_client: Any) -> None:
    """An error frame ends the receive loop."""

    class Socket:
        def __aiter__(self) -> Any:
            return self._messages()

        async def _messages(self) -> Any:
            yield aiohttp.WSMessage(aiohttp.WSMsgType.ERROR, None, None)
            yield aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, '{"type": "event"}', None)

    messages: list[dict[str, Any]] = []
    client = make_client()
    client.subscribe_events(messages.append)
    await client._ws_receive(Socket())  # type: ignore[arg-type]
    assert messages == []
