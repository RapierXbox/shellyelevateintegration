"""A local ShellyElevate app: protocol v1 over HTTPS/WSS and the legacy HTTP API (for the client tests)."""

from __future__ import annotations

import asyncio
import copy
import datetime
import hashlib
import json
from pathlib import Path
import ssl
from typing import Any

from aiohttp import WSMsgType, web
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from custom_components.shellyelevateintegration.api.client import pairing_proof

from ..const import INFO, LEGACY_ROOT, LEGACY_SETTINGS, SCHEMA, SETTINGS, STATE

TOKEN = "server-token"
CODE = "246810"
PAIRING_ID = "pairing-1"


def make_certificate(directory: Path, name: str) -> tuple[ssl.SSLContext, str]:
    """A self-signed certificate like the app creates; returns the server context and its fingerprint."""
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    cert_file = directory / f"{name}.crt"
    key_file = directory / f"{name}.key"
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_file, key_file)
    return context, hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


class AppServer:
    """What the app answers; tests change the attributes to make it misbehave."""

    def __init__(self) -> None:
        """Initialize with the X2 of tests/const.py."""
        self.info: dict[str, Any] = copy.deepcopy(INFO)
        self.state: dict[str, Any] = copy.deepcopy(STATE)
        self.settings: dict[str, Any] = copy.deepcopy(SETTINGS)
        self.schema: Any = copy.deepcopy(SCHEMA)
        self.token = TOKEN
        self.fingerprint = ""
        self.port = 0
        self.plain_port = 0
        self.hello_status = 200
        self.hello_delay = 0.0
        self.hello_body: Any = None
        self.pair_status = 200
        self.pair_body: dict[str, Any] | None = None
        self.html_error_on: set[str] = set()
        self.fail_command: dict[str, Any] | None = None
        self.ws_reject: int | None = None
        self.ws_greeting: list[Any] = []
        self.ws_answer_commands = True
        self.websockets: list[web.WebSocketResponse] = []
        self.ws_received: list[Any] = []
        self.ws_connects = 0
        self.requests: list[tuple[str, str]] = []
        self.compat_hint = True
        # legacy app
        self.legacy = False
        self.legacy_root: dict[str, Any] = dict(LEGACY_ROOT)
        self.legacy_settings: dict[str, Any] = copy.deepcopy(LEGACY_SETTINGS)
        self.legacy_values: dict[str, Any] = {
            "/device/relay?num=0": {"state": True},
            "/device/relay?num=1": {"state": False},
            "/device/input?num=0": {"state": False},
            "/device/night_mode": {"state": False},
            "/device/getTemperature": {"temperature": 21.5},
            "/device/getHumidity": {"humidity": -999},
            "/device/getLux": {"lux": "bad"},
            "/device/getProximity": {"distance": 0.2},
            "/device/dimmer": {"on": True, "brightness": 40, "power": 3.5},
            "/media/volume": {"volume": "0.6"},
        }
        self.legacy_posts: list[tuple[str, Any]] = []
        self.legacy_settings_echo = True
        self.legacy_down = False

    # ---------------------------------------------------------------- v1

    def _authorized(self, request: web.Request) -> bool:
        return request.headers.get("Authorization") == f"Bearer {self.token}"

    def _json(self, data: Any, status: int = 200) -> web.Response:
        return web.json_response(data, status=status)

    async def _v1(self, request: web.Request) -> web.StreamResponse:
        path = request.path.removeprefix("/api/v1")
        self.requests.append((request.method, path))
        if path == "/hello":
            if self.hello_delay:
                await asyncio.sleep(self.hello_delay)
            if self.hello_body is not None:
                return web.Response(
                    text=self.hello_body if isinstance(self.hello_body, str) else json.dumps(self.hello_body),
                    status=self.hello_status,
                )
            hello = {
                key: value for key, value in self.info.items() if key not in ("android", "privileged", "capabilities")
            }
            return self._json({**hello, "paired": True}, self.hello_status)
        if path == "/pair" and request.method == "POST":
            if self.pair_body is not None or self.pair_status != 200:
                return self._json(self.pair_body or {}, self.pair_status)
            body = await request.json()
            assert body["client_id"] and body["client_name"]
            return self._json({"pairing_id": PAIRING_ID})
        if path == "/pair/confirm":
            body = await request.json()
            if body["proof"] != pairing_proof(CODE, PAIRING_ID, self.fingerprint):
                return self._json({"error": "invalid_code", "message": "wrong code"}, 403)
            return self._json({"token": self.token})
        if not self._authorized(request):
            return self._json({"error": "unauthorized"}, 401)
        if path in self.html_error_on:
            return web.Response(text="<html>oops</html>", status=502, content_type="text/html")
        if path == "/info":
            return self._json(self.info)
        if path == "/state":
            return self._json({"state": self.state})
        if path == "/settings" and request.method == "GET":
            return self._json({"settings": self.settings})
        if path == "/settings" and request.method == "PATCH":
            changes = await request.json()
            ignored = [key for key in changes if key not in self.settings]
            self.settings.update({k: v for k, v in changes.items() if k not in ignored})
            return self._json({"settings": self.settings, "ignored": ignored})
        if path == "/settings/schema":
            return self._json({"schema": self.schema})
        if path == "/command":
            body = await request.json()
            if self.fail_command is not None:
                return self._json({"success": False, **self.fail_command}, 400)
            return self._json({"success": True, "data": {"action": body["action"], **body["params"]}})
        if path == "/screenshot":
            return web.Response(body=b"\x89PNG-server", content_type="image/png")
        if path == "/logs":
            return web.Response(text=f"{request.query['lines']} lines\n")
        if path == "/pair" and request.method == "DELETE":
            return self._json({"success": True})
        if path == "/pair/rotate":
            self.token = "rotated-token"
            return self._json({"token": self.token})
        if path == "/ws":
            return await self._ws(request)
        return self._json({"error": "not_found"}, 404)

    async def _ws(self, request: web.Request) -> web.StreamResponse:
        if self.ws_reject is not None:
            return self._json({"error": "rejected"}, self.ws_reject)
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.ws_connects += 1
        self.websockets.append(ws)
        for message in self.ws_greeting:
            if isinstance(message, bytes):
                await ws.send_bytes(message)
            elif isinstance(message, str):
                await ws.send_str(message)
            else:
                await ws.send_json(message)
        async for msg in ws:
            if msg.type is not WSMsgType.TEXT:
                self.ws_received.append(msg.data)
                continue
            data = msg.json()
            self.ws_received.append(data)
            if data.get("type") == "command" and self.ws_answer_commands:
                if self.fail_command is not None:
                    await ws.send_json({"type": "result", "id": data["id"], "success": False, **self.fail_command})
                else:
                    await ws.send_json(
                        {"type": "result", "id": data["id"], "success": True, "data": {"action": data["action"]}}
                    )
        self.websockets.remove(ws)
        return ws

    async def push(self, message: Any) -> None:
        """Send a message to every connected WebSocket."""
        for ws in list(self.websockets):
            if isinstance(message, bytes):
                await ws.send_bytes(message)
            else:
                await ws.send_json(message)

    async def close_websockets(self) -> None:
        """Drop the WebSocket connections."""
        for ws in list(self.websockets):
            await ws.close()

    # ---------------------------------------------------------------- plain HTTP (compat server and legacy app)

    async def _plain(self, request: web.Request) -> web.StreamResponse:
        path = request.path_qs
        self.requests.append((request.method, f"plain {path}"))
        if self.legacy_down:
            return web.Response(status=503)
        if request.path == "/plain-text":
            return web.Response(text="not json")
        if request.path == "/api/v1/hello":
            if not self.legacy and self.compat_hint:
                return self._json({"tls_port": self.port})
            return self._json({"error": "not_found"}, 404)
        if request.path == "/" and request.method == "GET":
            return self._json(self.legacy_root) if self.legacy else self._json({}, 404)
        if request.path == "/settings":
            if request.method == "POST":
                changes = json.loads(await request.text())
                self.legacy_posts.append(("/settings", changes))
                self.legacy_settings.update(changes)
                if self.legacy_settings_echo:
                    return self._json({"success": True, "settings": self.legacy_settings})
                return self._json({"success": True})
            return self._json({"settings": self.legacy_settings})
        if request.method == "POST" or path == "/webview/refresh":
            text = await request.text()
            self.legacy_posts.append((path, json.loads(text) if text else None))
            return self._json({"success": True})
        if path in self.legacy_values:
            value = self.legacy_values[path]
            if isinstance(value, int):
                return self._json({"success": False, "error": "no sensor"}, value)
            return self._json(value)
        return self._json({"success": False, "error": "unknown"}, 404)


async def start(server: AppServer, tls: ssl.SSLContext | None) -> tuple[web.AppRunner, int]:
    """Serve the app on a free local port."""
    app = web.Application()
    handler = server._v1 if tls is not None else server._plain
    app.router.add_route("*", "/{tail:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0, ssl_context=tls)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]
    return runner, port


async def silent_server() -> tuple[asyncio.Server, int]:
    """A server that accepts connections and never answers."""

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await reader.read()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]
