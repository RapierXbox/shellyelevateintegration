"""Fixtures for the API client tests: a local app over TLS and plain HTTP."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import aiohttp
from homeassistant.core import HomeAssistant
import pytest

from .server import AppServer, make_certificate, start


@pytest.fixture(autouse=True)
def local_sockets(socket_enabled: None) -> None:
    """The local test app needs real sockets (still only to 127.0.0.1)."""


@pytest.fixture
async def session() -> AsyncGenerator[aiohttp.ClientSession]:
    """A client session like the one Home Assistant passes in."""
    async with aiohttp.ClientSession() as client_session:
        yield client_session


@pytest.fixture
async def app_server(hass: HomeAssistant, tmp_path: Path) -> AsyncGenerator[AppServer]:
    """The app: protocol v1 over TLS and its compatibility server over plain HTTP."""
    server = AppServer()
    tls, server.fingerprint = make_certificate(tmp_path, "display")
    v1_runner, server.port = await start(server, tls)
    plain_runner, server.plain_port = await start(server, None)
    yield server
    await server.close_websockets()
    await plain_runner.cleanup()
    await v1_runner.cleanup()


@pytest.fixture
async def legacy_server(app_server: AppServer) -> AppServer:
    """The same host running the legacy app (no protocol v1 on the plain port)."""
    app_server.legacy = True
    return app_server


@pytest.fixture
async def impostor(hass: HomeAssistant, tmp_path: Path) -> AsyncGenerator[AppServer]:
    """Another device answering with its own certificate."""
    server = AppServer()
    tls, server.fingerprint = make_certificate(tmp_path, "impostor")
    runner, server.port = await start(server, tls)
    yield server
    await server.close_websockets()
    await runner.cleanup()
