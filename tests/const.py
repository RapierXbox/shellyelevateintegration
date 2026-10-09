"""Data of a realistic display (based on ApiInfo.java, StateHub.java and SettingsRegistry.java of the app)."""

from __future__ import annotations

import copy
from typing import Any

from custom_components.shellyelevateintegration.api.app_schema import APP_RULES

HOST = "192.168.1.50"
NEW_HOST = "192.168.1.77"
PORT = 8443
DEVICE_ID = "shellyelevate-4a2f"
OTHER_DEVICE_ID = "shellyelevate-9c1e"
FINGERPRINT = "ab" * 32
OTHER_FINGERPRINT = "cd" * 32
TOKEN = "f3Qn8Y2r1x-token"
MAC = "AA:BB:CC:DD:EE:FF"
TITLE = "Shelly Wall Display X2"
PAIRING_ID = "pair-1234"

HELLO = {
    "id": DEVICE_ID,
    "mac": MAC,
    "model": "SAWD-2A1XX10EU1",
    "codename": "PEGASUS",
    "name": TITLE,
    "fw": "3.26150.1200",
    "api": "1.0",
    "paired": False,
}

CAPABILITIES: dict[str, Any] = {
    "relays": 2,
    "optional_relays_from": 1,
    "inputs": 1,
    "buttons": 0,
    "proximity": True,
    "power_button": False,
    "dimmer": False,
    "temperature": True,
    "humidity": True,
    "lux": True,
    "speaker": True,
    "microphone": True,
    "bluetooth": True,
    "screenshot": True,
    "self_update": True,
}

INFO: dict[str, Any] = {
    **{key: value for key, value in HELLO.items() if key != "paired"},
    "android": "8.1.0",
    "privileged": True,
    "capabilities": CAPABILITIES,
}

STATE: dict[str, Any] = {
    "relay.0": False,
    "relay.1": True,
    "input.0": False,
    "lux": 120.5,
    "proximity": 3.2,
    "presence": False,
    "screen.on": True,
    "screen.brightness": 200,
    "screen.auto_brightness": True,
    "night_mode": False,
    "webview.url": "http://homeassistant.local:8123/lovelace/0",
    "temperature": 21.4,
    "humidity": 45.2,
    "uptime": 3600,
    "wifi.rssi": -55,
    "memory.free": 512,
    "cpu.temperature": 48.3,
    "voice.state": "idle",
    "voice.muted": False,
}

_RANGES: dict[str, dict[str, Any]] = {
    "screenSaverDelay": {"min": 5, "max": 86400, "step": 5, "unit": "s"},
    "minBrightness": {"min": 0, "max": 255},
    "brightness": {"min": 0, "max": 255},
    "screenSaverMinBrightness": {"min": 0, "max": 255},
    "proximityKeepAwakeSeconds": {"min": 0, "max": 86400, "step": 5},
    "voiceWakeSensitivity": {"min": 0, "max": 100, "step": 1},
    "voiceAssistantMaxRecordSeconds": {"min": 1, "max": 60},
    "mqttPort": {"min": 1, "max": 65535},
}


def _schema_item(rule: dict[str, Any]) -> dict[str, Any]:
    item = {**copy.deepcopy(rule), "label": rule["key"], "category": "general"}
    item |= _RANGES.get(rule["key"], {})
    if rule["key"] == "mqttPassword":
        item["secret"] = True
    if rule["key"] == "mqttDeviceId":
        item["per_device"] = True
    return item


SCHEMA: list[dict[str, Any]] = [_schema_item(rule) for rule in APP_RULES]
"""The settings schema of the current app: SettingsRegistry.java with its rules."""

SETTINGS: dict[str, Any] = {rule["key"]: copy.deepcopy(rule["default"]) for rule in APP_RULES} | {
    "webviewUrl": "http://homeassistant.local:8123/lovelace/0",
    "mqttBroker": "mqtt.local",
    "mqttUsername": "display",
    "mqttPassword": "hunter2",
    "mqttDeviceId": DEVICE_ID,
    # the features this integration turns on (see FEATURE_SWITCHES)
    "mediaEnabled": True,
    "haVoiceEnabled": True,
    "bleScannerEnabled": True,
    "httpServer": False,
}
"""Settings of a display that was set up with this integration."""

LEGACY_ROOT = {"modelName": "PEGASUS", "name": "Shelly Wall Display", "version": "2.4.1", "numOfInputs": 1}
LEGACY_SETTINGS: dict[str, Any] = {
    "webviewUrl": "http://homeassistant.local:8123/",
    "liteMode": False,
    "httpServer": True,
    "mqttDeviceId": "shellywalldisplay-legacy",
    "mqttEnabled": False,
    "mediaEnabled": "true",
    "automaticBrightness": True,
    "brightness": 180,
    "screenSaver": True,
    "screenSaverDelay": 45,
    "screenSaverId": 1,
    "voiceAssistantEnabled": False,
    "bluetoothProxyEnabled": False,
    "adbWifiEnabled": False,
}
LEGACY_DEVICE_ID = "shellywalldisplay-legacy"
LEGACY_PORT = 8080
