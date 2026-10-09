"""Bluetooth proxy."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.shellyelevateintegration.api import CHANNEL_BLE, BleAdvertisement, encode_ble_batch

from .common import FakeDisplay
from .conftest import setup_entry
from .const import MAC

ADVERT = bytes([2, 1, 6, 5, 9]) + b"Tag1" + bytes([3, 3, 0x0F, 0x18])


def _scanner(hass: HomeAssistant):
    return next((scanner for scanner in bluetooth.async_current_scanners(hass) if scanner.source == MAC.upper()), None)


async def test_scanner_registered(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """The display is an active remote scanner fed by WebSocket channel 0x02."""
    scanner = _scanner(hass)
    assert scanner is not None
    assert scanner.name.startswith(init_integration.title)
    assert scanner.current_mode is BluetoothScanningMode.ACTIVE
    assert scanner.requested_mode is BluetoothScanningMode.ACTIVE

    batch = encode_ble_batch(
        [
            BleAdvertisement(address="11:22:33:44:55:66", address_type=1, rssi=-60, data=ADVERT),
            BleAdvertisement(address="11:22:33:44:55:77", address_type=5, rssi=-70, data=ADVERT),
        ]
    )
    display.client.push_binary(CHANNEL_BLE, batch)
    await hass.async_block_till_done()
    info = bluetooth.async_last_service_info(hass, "11:22:33:44:55:66", connectable=False)
    assert info is not None
    assert info.name == "Tag1"
    assert info.rssi == -60
    assert info.source == MAC.upper()


async def test_scanner_follows_setting(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """Turning the proxy off unregisters the scanner."""
    display.client.push({"type": "settings_changed", "changes": {"bleScannerEnabled": False}})
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()
    assert _scanner(hass) is None


async def test_no_scanner_without_proxy(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """No scanner while the proxy is off, or without a MAC address the device id is the source."""
    display.settings["bleScannerEnabled"] = False
    await setup_entry(hass, mock_config_entry)
    assert _scanner(hass) is None


async def test_scanner_source_without_mac(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """Without a MAC address the display id is the source."""
    display.info["mac"] = ""
    await setup_entry(hass, mock_config_entry)
    assert any(scanner.source == mock_config_entry.unique_id for scanner in bluetooth.async_current_scanners(hass))
