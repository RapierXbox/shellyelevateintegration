"""Bluetooth proxy: BLE advertisements from the display as a remote HA scanner."""

from __future__ import annotations

from collections.abc import Callable
import time

from habluetooth import BaseHaRemoteScanner
from homeassistant.components.bluetooth import BluetoothScanningMode, async_register_scanner
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .api import CHANNEL_BLE, parse_ble_batch
from .const import DOMAIN
from .device import ShellyElevateIntegrationDevice

ADDRESS_TYPES = {0: "public", 1: "random"}


class ShellyElevateIntegrationBleScanner(BaseHaRemoteScanner):
    """Passive remote scanner fed from WebSocket channel 0x02."""

    @callback
    def async_on_batch(self, payload: bytes) -> None:
        """Feed a batch of advertisements."""
        now = time.monotonic()
        for adv in parse_ble_batch(payload):
            self._async_on_raw_advertisement(
                adv.address,
                adv.rssi,
                adv.data,
                {"address_type": ADDRESS_TYPES.get(adv.address_type, "public")},
                now,
            )


async def async_setup_bluetooth(hass: HomeAssistant, device: ShellyElevateIntegrationDevice) -> Callable[[], None]:
    """Register the display as a Bluetooth scanner. Returns an unload callback."""
    info = device.info
    source = dr.format_mac(info.mac).upper() if info.mac else device.device_id
    scanner = ShellyElevateIntegrationBleScanner(
        source,
        device.entry.title,
        connector=None,
        connectable=False,
        requested_mode=BluetoothScanningMode.PASSIVE,
        current_mode=BluetoothScanningMode.PASSIVE,
    )
    unsubs: list[Callable[[], None]] = [
        scanner.async_setup(),
        async_register_scanner(
            hass,
            scanner,
            source_domain=DOMAIN,
            source_model=info.model_name,
            source_config_entry_id=device.entry.entry_id,
            source_device_id=device.device_entry_id,
        ),
        device.client.subscribe_binary(CHANNEL_BLE, scanner.async_on_batch),
    ]

    @callback
    def _unload() -> None:
        for unsub in reversed(unsubs):
            unsub()

    return _unload
