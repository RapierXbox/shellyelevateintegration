"""ADB RSA key for Home Assistant (one key for all displays)."""

from __future__ import annotations

import asyncio
import base64
import struct
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from ..const import DOMAIN

if TYPE_CHECKING:
    from adb_shell.auth.sign_pythonrsa import PythonRSASigner

STORAGE_KEY = f"{DOMAIN}.adb_key"
STORAGE_VERSION = 1
DATA_ADB_KEY: HassKey[AdbKey] = HassKey(f"{DOMAIN}_adb_key")
_LOCK: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_adb_key_lock")

_MODULUS_SIZE = 2048 // 8
_MODULUS_WORDS = _MODULUS_SIZE // 4
_STRUCT = "<LL" + "B" * _MODULUS_SIZE + "B" * _MODULUS_SIZE + "L"


class AdbKey:
    """Private key (PEM) and public key in Android's adb_keys format."""

    def __init__(self, private_pem: str, public: str) -> None:
        """Initialize."""
        self.private_pem = private_pem
        self.public = public

    def signer(self) -> PythonRSASigner:
        """Return an adb-shell signer (blocking: parses the key)."""
        from adb_shell.auth.sign_pythonrsa import PythonRSASigner

        return PythonRSASigner(self.public, self.private_pem)


def _android_pubkey(key: rsa.RSAPrivateKey, comment: str) -> str:
    numbers = key.public_key().public_numbers()
    r32 = 1 << 32
    n0inv = r32 - pow(numbers.n % r32, -1, r32)
    rr = pow(1 << (_MODULUS_SIZE * 8), 2, numbers.n)
    packed = struct.pack(
        _STRUCT,
        _MODULUS_WORDS,
        n0inv,
        *numbers.n.to_bytes(_MODULUS_SIZE, "little"),
        *rr.to_bytes(_MODULUS_SIZE, "little"),
        numbers.e,
    )
    return f"{base64.b64encode(packed).decode()} {comment}"


def generate_key(comment: str = "homeassistant@shellyelevateintegration") -> AdbKey:
    """Generate a new 2048-bit key (blocking)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return AdbKey(private_pem, _android_pubkey(key, comment))


async def async_get_adb_key(hass: HomeAssistant) -> AdbKey:
    """Load or create Home Assistant's ADB key."""
    if (key := hass.data.get(DATA_ADB_KEY)) is not None:
        return key
    lock = hass.data.setdefault(_LOCK, asyncio.Lock())
    async with lock:
        if (key := hass.data.get(DATA_ADB_KEY)) is not None:
            return key
        store: Store[dict[str, str]] = Store(hass, STORAGE_VERSION, STORAGE_KEY, private=True)
        if data := await store.async_load():
            key = AdbKey(data["private"], data["public"])
        else:
            key = await hass.async_add_executor_job(generate_key)
            await store.async_save({"private": key.private_pem, "public": key.public})
        hass.data[DATA_ADB_KEY] = key
        return key
