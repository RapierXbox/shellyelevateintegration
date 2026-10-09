"""Data models, the client base class and errors."""

from __future__ import annotations

from typing import Any

from custom_components.shellyelevateintegration.api import (
    BleAdvertisement,
    Capabilities,
    DeviceInfo,
    MediaStatus,
    SettingDef,
    ShellyElevateIntegrationApi,
    ShellyElevateIntegrationCommandError,
    ShellyElevateIntegrationUnsupportedError,
    encode_ble_batch,
    model_name,
    parse_api_version,
    parse_ble_batch,
)
from custom_components.shellyelevateintegration.api.base import base_url

from ..const import INFO


def test_model_name() -> None:
    """Codename, SKU or a generic name."""
    assert model_name("pegasus") == "Wall Display X2"
    assert model_name(None, "SAWD-3A1XE10EU2") == "Wall Display XL"
    assert model_name("NEWONE") == "Wall Display (NEWONE)"
    assert model_name("unknown") == "Wall Display"
    assert model_name(None) == "Wall Display"


def test_device_info() -> None:
    """Unknown keys of a newer app are kept as reported, not as capabilities."""
    data: dict[str, Any] = {**INFO, "capabilities": {**INFO["capabilities"], "laser": True}, "future": 1}
    info = DeviceInfo.from_v1(data)
    assert info.model_name == "Wall Display X2"
    assert info.capabilities.relays == 2
    assert info.reported_capabilities["laser"] is True
    assert info.as_dict()["device_id"] == "shellyelevate-4a2f"
    assert DeviceInfo.from_v1({"id": "x", "capabilities": "nope"}).capabilities == Capabilities()
    assert DeviceInfo.from_v1({"id": "x"}).name == "Shelly Wall Display"


def test_media_status_and_settings() -> None:
    """Unknown keys are ignored; malformed rules are dropped."""
    status = MediaStatus.from_dict({"state": "playing", "volume": 0.5, "new_field": 1})
    assert status.as_dict()["state"] == "playing"
    item = SettingDef.from_dict(
        {"key": "a", "type": "bool", "visible_if": [{"key": "b", "eq": True}, "junk"], "requires": "junk", "x": 1}
    )
    assert item.visible_if == [{"key": "b", "eq": True}]
    assert item.requires is None
    assert item.as_dict()["key"] == "a"


def test_ble_batch_roundtrip() -> None:
    """BLE batches of channel 0x02; a truncated advertisement ends the batch."""
    adverts = [
        BleAdvertisement(address="AA:BB:CC:DD:EE:01", address_type=0, rssi=-40, data=b"\x02\x01\x06"),
        BleAdvertisement(address="AA:BB:CC:DD:EE:02", address_type=1, rssi=-90, data=b""),
    ]
    payload = encode_ble_batch(adverts)
    assert parse_ble_batch(payload) == adverts
    assert parse_ble_batch(payload[:-1]) == adverts[:1]  # an incomplete header is dropped
    assert parse_ble_batch(encode_ble_batch(adverts[:1])[:-1]) == []


def test_parse_api_version() -> None:
    """major.minor with fallbacks."""
    assert parse_api_version("1.2") == (1, 2)
    assert parse_api_version("2") == (2, 0)
    assert parse_api_version(None) == (0, 0)
    assert parse_api_version("x.y") == (0, 0)


def test_base_url() -> None:
    """IPv6 literals are bracketed."""
    assert base_url("fe80::1", 8443, tls=True) == "https://[fe80::1]:8443"
    assert base_url("[fe80::1]", 80) == "http://[fe80::1]:80"
    assert base_url("10.0.0.1", 8080) == "http://10.0.0.1:8080"


class _Client(ShellyElevateIntegrationApi):
    async def connect(self) -> Any:
        return None

    async def disconnect(self) -> None:
        return None

    async def command(self, action: str, /, **params: Any) -> dict[str, Any]:
        return {}

    async def get_settings(self) -> dict[str, Any]:
        return {}

    async def set_settings(self, changes: dict[str, Any]) -> Any:
        return None

    async def get_settings_schema(self) -> list[SettingDef]:
        return []


async def test_base_client() -> None:
    """Defaults of the base class and subscriber isolation."""
    client = _Client("h", 1)
    assert client.capabilities == Capabilities()
    assert await client.screenshot() is None
    assert await client.get_logs() is None
    await client.send_binary(1, b"")
    received: list[Any] = []

    def broken(*_args: Any) -> None:
        raise RuntimeError("subscriber bug")

    unsubs = [
        client.subscribe_state(broken),
        client.subscribe_state(received.append),
        client.subscribe_events(received.append),
        client.subscribe_connection(received.append),
        client.subscribe_binary(2, received.append),
    ]
    client._apply_state({"a": 1})
    client._apply_state({"a": 1})  # unchanged
    client._emit({"type": "voice.config", "active": []})
    client._emit({"type": "settings_changed", "changes": {"x": 1}})
    client._emit_binary(2, b"ble")
    client._set_connected(True)
    client._set_connected(True)
    assert received == [
        {"a": 1},
        {"type": "voice.config", "active": []},
        {"type": "settings_changed", "changes": {"x": 1}},
        b"ble",
        True,
    ]
    assert client.voice_config == {"type": "voice.config", "active": []}
    assert client.settings == {"x": 1}
    for unsub in unsubs:
        unsub()


def test_errors() -> None:
    """Error codes and messages."""
    assert str(ShellyElevateIntegrationCommandError("busy")) == "busy"
    assert str(ShellyElevateIntegrationCommandError("busy", "later")) == "busy: later"
    assert ShellyElevateIntegrationUnsupportedError().code == "unsupported"
