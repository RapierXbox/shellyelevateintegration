"""ShellyElevate local API clients.

This package has no Home Assistant imports so it can be split out into a PyPI library.
"""

from .base import ShellyElevateIntegrationApi
from .client import ShellyElevateIntegrationClient, async_pair_confirm, async_pair_start, async_probe
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
from .legacy import LegacyClient
from .models import (
    API_MAJOR,
    API_MINOR,
    CHANNEL_AUDIO,
    CHANNEL_BLE,
    DEFAULT_NAME,
    DEFAULT_PORT,
    LEGACY_PORT,
    MODELS,
    BleAdvertisement,
    Capabilities,
    DeviceInfo,
    Hello,
    MediaStatus,
    SettingDef,
    encode_ble_batch,
    model_name,
    parse_api_version,
    parse_ble_batch,
)

__all__ = [
    "API_MAJOR",
    "API_MINOR",
    "CHANNEL_AUDIO",
    "CHANNEL_BLE",
    "DEFAULT_NAME",
    "DEFAULT_PORT",
    "LEGACY_PORT",
    "MODELS",
    "BleAdvertisement",
    "Capabilities",
    "DeviceInfo",
    "Hello",
    "LegacyClient",
    "MediaStatus",
    "SettingDef",
    "ShellyElevateIntegrationApi",
    "ShellyElevateIntegrationAuthError",
    "ShellyElevateIntegrationCertificateError",
    "ShellyElevateIntegrationClient",
    "ShellyElevateIntegrationCommandError",
    "ShellyElevateIntegrationConnectionError",
    "ShellyElevateIntegrationError",
    "ShellyElevateIntegrationIncompatibleError",
    "ShellyElevateIntegrationPairingError",
    "ShellyElevateIntegrationUnsupportedError",
    "async_pair_confirm",
    "async_pair_start",
    "async_probe",
    "encode_ble_batch",
    "model_name",
    "parse_api_version",
    "parse_ble_batch",
]
