"""Client for the ShellyElevate local API v1 (HTTPS + WSS push, certificate pinned at pairing)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import contextlib
import hashlib
import hmac
import itertools
import logging
import ssl
import time
from typing import Any, Literal, overload

import aiohttp

from .app_schema import with_app_rules
from .base import ShellyElevateIntegrationApi, base_url
from .errors import (
    ShellyElevateIntegrationAuthError,
    ShellyElevateIntegrationCertificateError,
    ShellyElevateIntegrationCommandError,
    ShellyElevateIntegrationConnectionError,
    ShellyElevateIntegrationError,
    ShellyElevateIntegrationIncompatibleError,
    ShellyElevateIntegrationPairingError,
    ShellyElevateIntegrationUnsupportedError,
)
from .models import (
    API_MAJOR,
    DEFAULT_NAME,
    DEFAULT_PORT,
    LEGACY_PORT,
    DeviceInfo,
    Hello,
    SettingDef,
    SettingsWrite,
    parse_api_version,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10
HANDSHAKE_TIMEOUT = 5
COMMAND_TIMEOUT = 15
RECONNECT_MIN = 1
RECONNECT_MAX = 60
RECONNECT_STABLE = 30  # a connection must last this long before the backoff resets
HEARTBEAT = 30

PAIRING_CONTEXT = b"shellyelevate-pair-v1"


def pairing_proof(code: str, pairing_id: str, fingerprint: str) -> str:
    """Proof of the pairing code, bound to the certificate the client sees (protocol-v1.md, Pairing).

    The code itself never leaves the client, so a man in the middle presenting its own
    certificate cannot simply relay it: the display rejects a proof made for another certificate.
    """
    message = PAIRING_CONTEXT + b"\0" + pairing_id.encode() + b"\0" + bytes.fromhex(fingerprint)
    return hmac.new(code.strip().encode(), message, hashlib.sha256).hexdigest()


def _pinned(fingerprint: str | None) -> aiohttp.Fingerprint | None:
    """aiohttp check for a pinned certificate; None if the fingerprint is missing or malformed."""
    try:
        return aiohttp.Fingerprint(bytes.fromhex(fingerprint or ""))
    except ValueError:
        return None


_NO_VERIFY: ssl.SSLContext | None = None


def _no_verify_context() -> ssl.SSLContext:
    """TLS without CA checks: the certificate is checked by its pinned fingerprint instead."""
    global _NO_VERIFY
    if _NO_VERIFY is None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        _NO_VERIFY = context
    return _NO_VERIFY


async def _fetch_fingerprint(host: str, port: int) -> str:
    """SHA-256 of the certificate the server presents.

    The handshake proves the server holds the certificate's private key, so a matching
    fingerprint identifies the display even though no CA vouches for it.
    """
    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            # A plain HTTP server may just wait for a request line: that is "no TLS here", not
            # an unreachable host, so the handshake gets its own, shorter timeout.
            _reader, writer = await asyncio.open_connection(
                host, port, ssl=_no_verify_context(), ssl_handshake_timeout=HANDSHAKE_TIMEOUT
            )
    except TimeoutError as err:
        raise _ProbeTimeout(f"Cannot reach {host}: timeout") from err
    except (OSError, ssl.SSLError) as err:
        raise ShellyElevateIntegrationConnectionError(f"No TLS on {host}:{port}: {err}") from err
    try:
        ssl_object = writer.get_extra_info("ssl_object")
        der = ssl_object.getpeercert(binary_form=True) if ssl_object else None
    finally:
        writer.close()
    if not der:
        raise ShellyElevateIntegrationConnectionError(f"{host}:{port} presented no certificate")
    return hashlib.sha256(der).hexdigest()


class _ProbeTimeout(ShellyElevateIntegrationConnectionError):
    """The host did not answer at all; trying other ports would only add more timeouts."""


async def async_probe(
    session: aiohttp.ClientSession, host: str, port: int = DEFAULT_PORT, *, plain_first: bool = False
) -> Hello:
    """Identify the app on `host`: protocol v1 over TLS, or the legacy app over HTTP.

    Tried in order: v1 on `port`; the plain HTTP port (8080 unless another port was given),
    where an updated app's compatibility server names its TLS port and the legacy app answers
    `GET /`; finally v1 on the default port. `plain_first` (a known legacy host) swaps the first
    two, so a plain HTTP server is not sent a TLS handshake every time.
    """
    plain_port = LEGACY_PORT if port == DEFAULT_PORT else port
    attempts: list[Callable[[], Awaitable[Hello]]] = [
        lambda: _probe_v1(session, host, port),
        lambda: _probe_plain(session, host, plain_port),
    ]
    if plain_first:
        attempts.reverse()
    if port != DEFAULT_PORT:
        attempts.append(lambda: _probe_v1(session, host, DEFAULT_PORT))
    error: ShellyElevateIntegrationConnectionError | None = None
    for attempt in attempts:
        try:
            return await attempt()
        except _ProbeTimeout:
            raise  # the host does not answer at all; other ports would only add timeouts
        except ShellyElevateIntegrationConnectionError as err:
            error = err
    assert error is not None
    raise error


async def _probe_v1(session: aiohttp.ClientSession, host: str, port: int) -> Hello:
    """Unauthenticated hello over TLS; records the (not yet trusted) certificate fingerprint."""
    fingerprint = await _fetch_fingerprint(host, port)
    url = f"{base_url(host, port, tls=True)}/api/v1/hello"
    # a sha256 hex digest always parses (aiohttp treats a missing check as ssl=True)
    pinned = _pinned(fingerprint)
    try:
        async with session.get(
            url, ssl=True if pinned is None else pinned, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        ) as resp:
            if resp.status != 200:
                raise ShellyElevateIntegrationConnectionError(f"HTTP {resp.status} from {url}")
            data = await resp.json(content_type=None)
    except TimeoutError as err:
        raise _ProbeTimeout(f"Cannot reach {host}: timeout") from err
    except (aiohttp.ClientError, ValueError) as err:
        raise ShellyElevateIntegrationConnectionError(f"Cannot reach {url}: {err}") from err
    if not isinstance(data, dict) or not data.get("id"):
        raise ShellyElevateIntegrationConnectionError(f"{host}:{port} is not a ShellyElevate display")
    return Hello(
        device_id=str(data["id"]),
        name=data.get("name") or DEFAULT_NAME,
        model=data.get("model"),
        codename=data.get("codename"),
        fw_version=data.get("fw"),
        api_version=data.get("api"),
        mac=data.get("mac"),
        paired=bool(data.get("paired")),
        legacy=False,
        port=port,
        fingerprint=fingerprint,
    )


async def _probe_plain(session: aiohttp.ClientSession, host: str, port: int) -> Hello:
    """Plain HTTP: an updated app's compatibility server, or the legacy app."""
    base = base_url(host, port)
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    try:
        async with session.get(f"{base}/api/v1/hello", timeout=timeout) as resp:
            hint = await resp.json(content_type=None) if resp.status == 200 else None
        if isinstance(hint, dict) and hint.get("tls_port"):
            return await _probe_v1(session, host, int(hint["tls_port"]))
        # Legacy app: no /api/v1, but GET / returns {"modelName": ...}
        async with session.get(f"{base}/", timeout=timeout) as resp:
            if resp.status != 200:
                raise ShellyElevateIntegrationConnectionError(f"Unexpected HTTP {resp.status} from {host}")
            data = await resp.json(content_type=None)
        if not isinstance(data, dict) or "modelName" not in data:
            raise ShellyElevateIntegrationConnectionError(f"{host} is not a ShellyElevate display")
        async with session.get(f"{base}/settings", timeout=timeout) as resp:
            settings = (await resp.json(content_type=None)).get("settings", {}) if resp.status == 200 else {}
    except TimeoutError as err:
        raise _ProbeTimeout(f"Cannot reach {host}: timeout") from err
    except (aiohttp.ClientError, ValueError, KeyError, AttributeError) as err:
        raise ShellyElevateIntegrationConnectionError(f"Cannot reach {host}: {err}") from err
    device_id = settings.get("mqttDeviceId") or f"shellyelevate-{host.replace('.', '-')}"
    return Hello(
        device_id=device_id,
        name=data.get("name") or DEFAULT_NAME,
        model=None,
        codename=data.get("modelName"),
        fw_version=data.get("version"),
        api_version=None,
        mac=None,
        paired=False,
        legacy=True,
        port=port,
    )


async def async_pair_start(
    session: aiohttp.ClientSession,
    host: str,
    port: int,
    client_id: str,
    client_name: str = "Home Assistant",
    *,
    fingerprint: str,
) -> str:
    """Ask the display to show a pairing code. Returns the pairing id."""
    data = await _post_json(
        session,
        f"{base_url(host, port, tls=True)}/api/v1/pair",
        {"client_id": client_id, "client_name": client_name},
        fingerprint,
    )
    return _required(data, "pairing_id")


async def async_pair_confirm(
    session: aiohttp.ClientSession, host: str, port: int, pairing_id: str, code: str, *, fingerprint: str
) -> str:
    """Prove the code shown on the display for the certificate we pinned. Returns the token."""
    data = await _post_json(
        session,
        f"{base_url(host, port, tls=True)}/api/v1/pair/confirm",
        {"pairing_id": pairing_id, "proof": pairing_proof(code, pairing_id, fingerprint)},
        fingerprint,
    )
    return _required(data, "token")


async def _post_json(
    session: aiohttp.ClientSession, url: str, body: dict[str, Any], fingerprint: str
) -> dict[str, Any]:
    if (ssl := _pinned(fingerprint)) is None:
        raise ShellyElevateIntegrationCertificateError("No valid certificate fingerprint")
    try:
        async with session.post(url, json=body, ssl=ssl, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as resp:
            data = _object(await resp.json(content_type=None))
            if resp.status in (403, 410, 429):
                raise ShellyElevateIntegrationPairingError(str(data.get("error", "invalid_code")), data.get("message"))
            if resp.status != 200:
                raise ShellyElevateIntegrationConnectionError(f"HTTP {resp.status}: {data}")
            return data
    except aiohttp.ServerFingerprintMismatch as err:
        raise ShellyElevateIntegrationCertificateError(f"{url}: the display presented a different certificate") from err
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        raise ShellyElevateIntegrationConnectionError(str(err)) from err


def _required(data: dict[str, Any], key: str) -> str:
    if not isinstance(value := data.get(key), str) or not value:
        raise ShellyElevateIntegrationConnectionError(f"Invalid pairing response: no {key}")
    return value


def _with_transport_caps(info: DeviceInfo) -> DeviceInfo:
    caps = info.capabilities
    caps.push = caps.media_status = caps.settings_schema = True
    caps.voice = caps.microphone
    return info


class ShellyElevateIntegrationClient(ShellyElevateIntegrationApi):
    """Client for protocol v1."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int = DEFAULT_PORT,
        token: str = "",
        fingerprint: str | None = None,
        device_id: str | None = None,
    ) -> None:
        """Initialize. `fingerprint` is the certificate pinned at pairing; without it nothing is sent."""
        super().__init__(host, port)
        self._session = session
        self._token = token
        self._ssl = _pinned(fingerprint)
        self._device_id = device_id
        self._base = base_url(host, port, tls=True)
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ws_task: asyncio.Task[None] | None = None
        self._ids = itertools.count(1)
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._closing = False
        self._first_state = asyncio.Event()
        self._settings_task: asyncio.Task[None] | None = None
        self._incompatible = False

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    # ---------------------------------------------------------------- HTTP

    @overload
    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        raw: Literal[False] = False,
    ) -> Any: ...
    @overload
    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        raw: Literal[True],
    ) -> bytes: ...
    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        raw: bool = False,
    ) -> Any:
        if self._ssl is None:
            # Never send the token over a connection whose certificate we cannot check.
            raise ShellyElevateIntegrationCertificateError("No pinned certificate; pair again")
        try:
            async with self._session.request(
                method,
                f"{self._base}{path}",
                json=json,
                params=params,
                headers=self._headers,
                ssl=self._ssl,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status == 401:
                    raise ShellyElevateIntegrationAuthError("Token rejected")
                if raw:
                    if resp.status != 200:
                        raise ShellyElevateIntegrationCommandError(str(resp.status))
                    return await resp.read()
                try:
                    data = await resp.json(content_type=None)
                except ValueError as err:  # an HTML error page from the app or a proxy
                    raise ShellyElevateIntegrationCommandError(str(resp.status), "invalid JSON response") from err
                if resp.status >= 400 or (isinstance(data, dict) and data.get("success") is False):
                    code = data.get("error", str(resp.status)) if isinstance(data, dict) else str(resp.status)
                    message = data.get("message") if isinstance(data, dict) else None
                    if code == "unsupported":
                        raise ShellyElevateIntegrationUnsupportedError(message)
                    raise ShellyElevateIntegrationCommandError(code, message)
                return data
        except aiohttp.ServerFingerprintMismatch as err:
            raise ShellyElevateIntegrationCertificateError(f"{self.host} presented a different certificate") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ShellyElevateIntegrationConnectionError(f"{method} {path} failed: {err}") from err

    async def get_info(self) -> DeviceInfo:
        """Fetch device info (authenticated, so this also checks the token)."""
        data = await self._request("GET", "/api/v1/info")
        if not isinstance(data, dict):
            raise ShellyElevateIntegrationCommandError("invalid_response", "info is not an object")
        try:
            return DeviceInfo.from_v1(data)
        except (KeyError, TypeError, ValueError) as err:
            raise ShellyElevateIntegrationCommandError("invalid_response", f"bad info: {err}") from err

    async def connect(self) -> DeviceInfo:
        """Fetch info + settings, then start the WebSocket."""
        try:
            info = await self.get_info()
        except ShellyElevateIntegrationCertificateError:
            if self._ssl is not None and not await self._same_display_new_certificate():
                # e.g. after a DHCP shuffle: not ours, so no reason to pair again; retry later
                raise ShellyElevateIntegrationConnectionError(f"Another display answers at {self.host}") from None
            raise
        major, _minor = parse_api_version(info.api_version)
        if major != API_MAJOR:
            raise ShellyElevateIntegrationIncompatibleError(
                f"Display speaks API {info.api_version}, expected {API_MAJOR}.x"
            )
        self.info = _with_transport_caps(info)
        state = await self._request("GET", "/api/v1/state")
        self._apply_state(_object(_object(state).get("state")), snapshot=True)
        await self.get_settings()
        self._set_connected(True)
        self._closing = False
        self._ws_task = asyncio.create_task(self._ws_loop(), name=f"shellyelevateintegration ws {self.host}")
        return info

    async def _same_display_new_certificate(self) -> bool:
        """After a certificate mismatch: is it this display with a new key (re-pair), or another device?"""
        expected = self.info.device_id if self.info else self._device_id
        try:
            hello = await _probe_v1(self._session, self.host, self.port)
        except ShellyElevateIntegrationConnectionError:
            return False
        return expected is not None and hello.device_id == expected

    async def rotate_token(self) -> str:
        """Replace our token with a new one (protocol §3c); the old one stops working."""
        data = await self._request("POST", "/api/v1/pair/rotate")
        self._token = _required(_object(data), "token")
        return self._token

    async def disconnect(self) -> None:
        """Close the WebSocket."""
        self._closing = True
        if self._settings_task is not None:
            self._settings_task.cancel()
        if self._ws is not None:
            await self._ws.close()
        if self._ws_task is not None:
            self._ws_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ws_task
            self._ws_task = None
        self._fail_pending(ShellyElevateIntegrationConnectionError("Disconnected"))
        self._set_connected(False)

    async def command(self, action: str, /, **params: Any) -> dict[str, Any]:
        """Run a command, over the WebSocket if it is up, otherwise HTTP."""
        if self._ws is not None and not self._ws.closed:
            msg_id = next(self._ids)
            fut: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
            self._pending[msg_id] = fut
            try:
                await self._ws.send_json({"type": "command", "id": msg_id, "action": action, "params": params})
                async with asyncio.timeout(COMMAND_TIMEOUT):
                    result = await fut
            except (aiohttp.ClientError, ConnectionResetError) as err:
                raise ShellyElevateIntegrationConnectionError(str(err)) from err
            except TimeoutError as err:
                raise ShellyElevateIntegrationConnectionError(f"Command {action} timed out") from err
            finally:
                self._pending.pop(msg_id, None)
            if not result.get("success", False):
                code = result.get("error", "internal")
                if code == "unsupported":
                    raise ShellyElevateIntegrationUnsupportedError(result.get("message"))
                raise ShellyElevateIntegrationCommandError(code, result.get("message"))
            return result.get("data") or {}
        data = await self._request("POST", "/api/v1/command", json={"action": action, "params": params})
        return _object(_object(data).get("data"))

    async def get_settings(self) -> dict[str, Any]:
        """Return all settings."""
        data = await self._request("GET", "/api/v1/settings")
        self.settings = dict(_object(_object(data).get("settings")))
        return self.settings

    async def set_settings(self, changes: dict[str, Any]) -> SettingsWrite:
        """Apply partial settings; keys the display does not know come back in `ignored`."""
        data = _object(await self._request("PATCH", "/api/v1/settings", json=changes))
        self.settings = dict(_object(data.get("settings")))
        ignored = data.get("ignored")
        ignored = [key for key in ignored if isinstance(key, str)] if isinstance(ignored, list) else []
        applied = {key: self.settings.get(key) for key in changes if key not in ignored}
        return SettingsWrite(self.settings, applied, ignored)

    async def get_settings_schema(self) -> list[SettingDef]:
        """Return the settings schema."""
        data = await self._request("GET", "/api/v1/settings/schema")
        schema = _object(data).get("schema")
        if not isinstance(schema, list):
            return []
        result = []
        for item in schema:
            try:
                result.append(SettingDef.from_dict(item))
            except (TypeError, ValueError, AttributeError):
                _LOGGER.debug("Ignoring invalid schema item from %s: %s", self.host, item)
        return with_app_rules(result)

    async def screenshot(self) -> bytes | None:
        """Return a PNG."""
        return await self._request("GET", "/api/v1/screenshot", raw=True)

    async def get_logs(self, lines: int = 500) -> str | None:
        """Return recent app log lines."""
        data = await self._request("GET", "/api/v1/logs", params={"lines": lines}, raw=True)
        return data.decode(errors="replace")

    async def revoke(self) -> None:
        """Revoke our token on the display."""
        await self._request("DELETE", "/api/v1/pair")

    async def send_binary(self, channel: int, payload: bytes) -> None:
        """Send a binary frame."""
        if self._ws is None or self._ws.closed:
            raise ShellyElevateIntegrationConnectionError("WebSocket not connected")
        await self._ws.send_bytes(bytes([channel]) + payload)

    # ---------------------------------------------------------------- WebSocket

    async def _ws_loop(self) -> None:
        # connect starts this only after a request over the pinned certificate went through
        assert self._ssl is not None
        pinned = self._ssl
        delay = RECONNECT_MIN
        # checked at the end of each attempt (disconnect cancels this task while it waits)
        while True:
            opened: float | None = None
            try:
                async with self._session.ws_connect(
                    f"{self._base}/api/v1/ws",
                    headers=self._headers,
                    ssl=pinned,
                    heartbeat=HEARTBEAT,
                    timeout=aiohttp.ClientWSTimeout(ws_close=REQUEST_TIMEOUT),
                ) as ws:
                    self._ws = ws
                    opened = time.monotonic()
                    await self._ws_receive(ws)
            except aiohttp.ServerFingerprintMismatch:
                if await self._same_display_new_certificate():
                    _LOGGER.error("Display %s presented a different certificate; pair it again", self.host)
                    self._set_connected(False)
                    self._emit({"type": "_auth_failed"})
                    return
                # Another device answers on this address (pinned, so nothing was sent); keep trying.
                _LOGGER.warning("Another device answers at %s; retrying", self.host)
            except aiohttp.WSServerHandshakeError as err:
                if err.status == 401:
                    _LOGGER.error("Display %s rejected the token", self.host)
                    self._set_connected(False)
                    self._emit({"type": "_auth_failed"})
                    return
                _LOGGER.debug("WS handshake to %s failed: %s", self.host, err)
            except (aiohttp.ClientError, TimeoutError, ConnectionResetError) as err:
                _LOGGER.debug("WS connection to %s failed: %s", self.host, err)
            except Exception:
                # Never let the push channel die for good; reconnect instead.
                _LOGGER.warning("Unexpected error on the WebSocket to %s", self.host, exc_info=True)
            finally:
                self._ws = None
                self._fail_pending(ShellyElevateIntegrationConnectionError("WebSocket closed"))
            if self._closing:
                break
            self._set_connected(False)
            if opened is not None and time.monotonic() - opened >= RECONNECT_STABLE:
                delay = RECONNECT_MIN  # it was a healthy connection; a connect/close flap keeps backing off
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX)

    async def _ws_receive(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = msg.json()
                except ValueError:
                    _LOGGER.debug("Invalid JSON from %s: %s", self.host, msg.data)
                    continue
                if not isinstance(data, dict):
                    _LOGGER.debug("Ignoring non-object message from %s: %s", self.host, msg.data)
                    continue
                try:
                    self._handle_message(data)
                except Exception:
                    _LOGGER.warning("Ignoring malformed %s message from %s", data.get("type"), self.host, exc_info=True)
            elif msg.type == aiohttp.WSMsgType.BINARY:
                if msg.data:
                    self._emit_binary(msg.data[0], msg.data[1:])
            elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                break

    def _handle_message(self, data: dict[str, Any]) -> None:
        if self._incompatible:
            return
        msg_type = data.get("type")
        if msg_type == "hello":
            if isinstance(info := data.get("info"), dict):
                new = DeviceInfo.from_v1(info)
                if parse_api_version(new.api_version)[0] != API_MAJOR:
                    # Stop using it; the reload this triggers closes the socket and reports the error.
                    _LOGGER.error("%s now speaks API %s, not %s.x", self.host, new.api_version, API_MAJOR)
                    self._incompatible = True
                    self._set_connected(False)
                    self._emit({"type": "_incompatible"})
                    return
                old = self.info
                self.info = _with_transport_caps(new)
                if old is not None and (
                    new.fw_version != old.fw_version
                    or new.capabilities != old.capabilities
                    or new.reported_capabilities != old.reported_capabilities
                ):
                    self._emit({"type": "_info_changed"})
            # Settings may have changed while we were away; their echoes are lost.
            self._schedule_settings_refresh()
        elif msg_type == "state":
            # Available first: listeners (the thermostat) act on the snapshot only when available.
            self._set_connected(True)
            self._apply_state(_object(data.get("state")), snapshot=True)
        elif msg_type == "state_delta":
            self._apply_state(_object(data.get("changes")))
        elif msg_type == "result":
            msg_id = data.get("id")
            fut = self._pending.get(msg_id) if isinstance(msg_id, int) else None
            if fut is not None and not fut.done():
                fut.set_result(data)
        elif msg_type == "pong":
            pass
        elif msg_type == "settings_changed" and None in _object(data.get("changes")).values():
            # `null` means "reset to default"; fetch the resolved values instead of caching None.
            self._schedule_settings_refresh()
        else:
            self._emit(data)

    def _schedule_settings_refresh(self) -> None:
        if self._settings_task is None or self._settings_task.done():
            self._settings_task = asyncio.get_running_loop().create_task(
                self._refresh_settings(), name=f"shellyelevateintegration settings {self.host}"
            )

    async def _refresh_settings(self) -> None:
        """Re-read all settings and report the keys that changed."""
        old = dict(self.settings)
        try:
            await self.get_settings()
        except ShellyElevateIntegrationError as err:
            _LOGGER.debug("Could not refresh the settings of %s: %s", self.host, err)
            return
        if changed := {k: v for k, v in self.settings.items() if k not in old or old[k] != v}:
            self._emit({"type": "settings_changed", "changes": changed})

    def _fail_pending(self, err: Exception) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(err)
        self._pending.clear()


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
