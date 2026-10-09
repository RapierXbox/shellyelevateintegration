"""ADB key, stock-value store and the EOF-safe transport."""

from __future__ import annotations

import base64
from typing import Any
from unittest.mock import AsyncMock, patch

from adb_shell.adb_device_async import AdbDeviceAsync
from homeassistant.core import HomeAssistant
import pytest

from custom_components.shellyelevateintegration.adb.baseline import BaselineStore, async_get_baseline_store
from custom_components.shellyelevateintegration.adb.keys import (
    DATA_ADB_KEY,
    STORAGE_KEY,
    async_get_adb_key,
    generate_key,
)
from custom_components.shellyelevateintegration.adb.transport import (
    AdbConnectionClosed,
    EofSafeTcpTransport,
    create_device,
)


async def test_adb_key_created_once(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Home Assistant has one ADB key, stored privately."""
    key = await async_get_adb_key(hass)
    assert key is await async_get_adb_key(hass)
    assert key.public.endswith(" homeassistant@shellyelevateintegration")
    packed = base64.b64decode(key.public.split()[0])
    assert len(packed) == 524  # Android's RSAPublicKey struct for 2048 bits
    assert key.private_pem.startswith("-----BEGIN PRIVATE KEY-----")
    assert key.signer() is not None
    await hass.async_block_till_done()
    assert hass_storage[STORAGE_KEY]["data"]["public"] == key.public


async def test_adb_key_loaded(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """A stored key is used again."""
    stored = generate_key("test")
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "key": STORAGE_KEY,
        "data": {"private": stored.private_pem, "public": stored.public},
    }
    key = await async_get_adb_key(hass)
    assert key.public == stored.public
    hass.data.pop(DATA_ADB_KEY)
    # the lock is held while another caller loads it
    assert (await async_get_adb_key(hass)).public == stored.public


async def test_adb_key_concurrent(hass: HomeAssistant) -> None:
    """Two callers at once get the same key."""
    import asyncio

    first, second = await asyncio.gather(async_get_adb_key(hass), async_get_adb_key(hass))
    assert first is second


async def test_baseline_store(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """The first capture of stock values wins; a revert forgets them."""
    store = await async_get_baseline_store(hass)
    assert store is await async_get_baseline_store(hass)
    assert store.get("SER1") is None
    assert store.get(None) is None
    await store.async_capture("SER1", {"screen_brightness": "100"})
    await store.async_capture("SER1", {"screen_brightness": "255"})
    assert store.get("SER1") == {"screen_brightness": "100"}
    loaded = BaselineStore(hass)
    await loaded.async_load()
    assert loaded.get("SER1") == {"screen_brightness": "100"}
    await store.async_remove("SER1")
    await store.async_remove("SER1")
    assert store.get("SER1") is None


async def test_transport_raises_on_eof() -> None:
    """An empty read means the display closed the connection."""
    transport = EofSafeTcpTransport("10.0.0.1", 5555)
    with patch("adb_shell.transport.tcp_transport_async.TcpTransportAsync.bulk_read", AsyncMock(return_value=b"")):
        with pytest.raises(AdbConnectionClosed):
            await transport.bulk_read(24, 1)
        assert await transport.bulk_read(0, 1) == b""
    with patch("adb_shell.transport.tcp_transport_async.TcpTransportAsync.bulk_read", AsyncMock(return_value=b"data")):
        assert await transport.bulk_read(4, 1) == b"data"
    assert isinstance(create_device("10.0.0.1", 5555), AdbDeviceAsync)
