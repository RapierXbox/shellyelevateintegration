"""Data models shared by the v1 and legacy clients."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any

API_MAJOR = 1
API_MINOR = 0
DEFAULT_PORT = 8443
"""Protocol v1: HTTPS and WSS with a self-signed certificate that clients pin."""
LEGACY_PORT = 8080
"""Plain HTTP: the legacy app's API, and the compatibility server of an updated app."""
DEFAULT_NAME = "Shelly Wall Display"

# WebSocket binary channels (first byte of every binary frame)
CHANNEL_AUDIO = 0x01
CHANNEL_BLE = 0x02

# Codename table from ShellyElevate's DeviceModel.java.
# codename: (sku, friendly name, relays, inputs, buttons, proximity, power_button)
MODELS: dict[str, tuple[str, str, int, int, int, bool, bool]] = {
    "STARGATE": ("SAWD-0A1XX10EU1", "Wall Display", 1, 1, 0, False, False),
    "ATLANTIS": ("SAWD-1A1XX10EU1", "Wall Display 2", 1, 1, 0, True, False),
    "PEGASUS": ("SAWD-2A1XX10EU1", "Wall Display X2", 2, 1, 0, True, False),
    "BLAKE": ("SAWD-3A1XE10EU2", "Wall Display XL", 2, 1, 4, True, True),
    "MAVERICK": ("SAWD-4A1XE10US0", "Wall Display U1", 1, 1, 0, True, True),
    "JENNA": ("SAWD-5A1XX10EU0", "Wall Display X2i", 2, 1, 0, True, True),
    "CALLY": ("SAWD-6A1XX10EU0", "Wall Display X1i", 2, 1, 0, True, True),
    "DAYNA": ("SAWD-6A0XX0EU0", "Wall Display D1", 0, 0, 0, True, True),
}

# The second relay of these models only exists with the optional 2-output power base; the
# app cannot tell, so relay 2 is created disabled (the user enables it if the base is fitted).
POWER_BASE_MODELS = frozenset({"PEGASUS", "BLAKE", "JENNA", "CALLY"})

_SKU_TO_CODENAME = {sku: codename for codename, (sku, *_rest) in MODELS.items()}


def model_name(codename: str | None, sku: str | None = None) -> str:
    """Return a friendly model name."""
    if codename and codename.upper() in MODELS:
        return MODELS[codename.upper()][1]
    if sku and sku in _SKU_TO_CODENAME:
        return MODELS[_SKU_TO_CODENAME[sku]][1]
    if codename and codename.upper() not in ("", "UNKNOWN"):
        return f"Wall Display ({codename})"
    return "Wall Display"


def _known_fields(cls: type, data: dict[str, Any]) -> dict[str, Any]:
    """Drop keys the dataclass does not know, so newer displays can add fields."""
    known = {item.name for item in fields(cls)}
    return {key: value for key, value in data.items() if key in known}


@dataclass(slots=True)
class Capabilities:
    """What a display can do."""

    relays: int = 0
    optional_relays_from: int | None = None
    """Relays from this index on may not exist (power base); their entities start disabled."""
    inputs: int = 0
    buttons: int = 0
    proximity: bool = False
    power_button: bool = False
    dimmer: bool = False
    temperature: bool = False
    humidity: bool = False
    lux: bool = False
    speaker: bool = False
    microphone: bool = False
    bluetooth: bool = False
    screenshot: bool = False
    self_update: bool = False
    # Transport features (not reported by the display, set by the client)
    media_status: bool = False
    voice: bool = False
    push: bool = False
    settings_schema: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Capabilities:
        """Build from the `capabilities` object, ignoring unknown keys."""
        return cls(**_known_fields(cls, data))

    def as_dict(self) -> dict[str, Any]:
        """Return a dict."""
        return asdict(self)


@dataclass(slots=True)
class DeviceInfo:
    """Identity of a display."""

    device_id: str
    name: str
    model: str | None  # SKU
    codename: str | None
    fw_version: str | None
    api_version: str | None
    mac: str | None = None
    android: str | None = None
    privileged: bool = False
    legacy: bool = False
    capabilities: Capabilities = field(default_factory=Capabilities)

    @property
    def model_name(self) -> str:
        """Friendly model name."""
        return model_name(self.codename, self.model)

    @classmethod
    def from_v1(cls, data: dict[str, Any]) -> DeviceInfo:
        """Build from a v1 `Info` object."""
        return cls(
            device_id=data["id"],
            name=data.get("name") or DEFAULT_NAME,
            model=data.get("model"),
            codename=data.get("codename"),
            fw_version=data.get("fw"),
            api_version=data.get("api"),
            mac=data.get("mac"),
            android=data.get("android"),
            privileged=bool(data.get("privileged")),
            capabilities=Capabilities.from_dict(data.get("capabilities") or {}),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a dict."""
        return asdict(self)


@dataclass(slots=True)
class MediaStatus:
    """Playback status reported by the display."""

    state: str = "idle"
    url: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    artwork: str | None = None
    position: float | None = None
    duration: float | None = None
    volume: float | None = None
    muted: bool = False
    repeat: str = "off"
    queue_size: int = 0
    announcing: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MediaStatus:
        """Build from a `MediaStatus` object, ignoring unknown keys."""
        return cls(**_known_fields(cls, data))

    def as_dict(self) -> dict[str, Any]:
        """Return a dict."""
        return asdict(self)


@dataclass(slots=True)
class SettingDef:
    """Definition of one display setting."""

    key: str
    type: str
    default: Any = None
    label: str | None = None
    description: str | None = None
    category: str = "general"
    min: float | None = None
    max: float | None = None
    step: float | None = None
    unit: str | None = None
    options: list[dict[str, Any]] | None = None
    secret: bool = False
    per_device: bool = False
    requires_restart: bool = False
    deprecated: bool = False
    """The setting belongs to a feature the app will remove."""
    replaced_by: str | None = None
    """Key of the setting that replaces it, if any."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SettingDef:
        """Build from a `SettingDef` object, ignoring unknown keys."""
        return cls(**_known_fields(cls, data))

    def as_dict(self) -> dict[str, Any]:
        """Return a dict."""
        return asdict(self)


@dataclass(slots=True)
class Hello:
    """Result of probing a host."""

    device_id: str
    name: str
    model: str | None
    codename: str | None
    fw_version: str | None
    api_version: str | None
    mac: str | None
    paired: bool
    legacy: bool
    port: int = DEFAULT_PORT
    """Port the app answered on (v1: TLS port; legacy: HTTP port)."""
    fingerprint: str | None = None
    """v1: SHA-256 of the certificate the display presented (lowercase hex, unpinned)."""


@dataclass(slots=True)
class BleAdvertisement:
    """One BLE advertisement from WS channel 0x02."""

    address: str
    address_type: int
    rssi: int
    data: bytes


def parse_ble_batch(payload: bytes) -> list[BleAdvertisement]:
    """Parse a channel 0x02 payload (without the channel byte)."""
    adverts: list[BleAdvertisement] = []
    pos = 0
    end = len(payload)
    while pos + 9 <= end:
        addr = payload[pos : pos + 6]
        addr_type = payload[pos + 6]
        rssi = int.from_bytes(payload[pos + 7 : pos + 8], "big", signed=True)
        length = payload[pos + 8]
        pos += 9
        if pos + length > end:
            break
        adverts.append(
            BleAdvertisement(
                address=":".join(f"{b:02X}" for b in addr),
                address_type=addr_type,
                rssi=rssi,
                data=bytes(payload[pos : pos + length]),
            )
        )
        pos += length
    return adverts


def encode_ble_batch(adverts: list[BleAdvertisement]) -> bytes:
    """Encode advertisements as a channel 0x02 payload (without the channel byte)."""
    out = bytearray()
    for adv in adverts:
        out += bytes(int(part, 16) for part in adv.address.split(":"))
        out.append(adv.address_type & 0xFF)
        out += adv.rssi.to_bytes(1, "big", signed=True)
        out.append(len(adv.data))
        out += adv.data
    return bytes(out)


def parse_api_version(version: str | None) -> tuple[int, int]:
    """Parse `major.minor`."""
    if not version:
        return (0, 0)
    major, _, minor = version.partition(".")
    try:
        return (int(major), int(minor or 0))
    except ValueError:
        return (0, 0)
