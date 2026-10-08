"""Settings schema for the legacy app (which has no schema endpoint).

Mirrors Constants.java / the Configuration-Reference wiki page of ShellyElevate.
"""

from __future__ import annotations

from typing import Any


def _s(key: str, type_: str, default: Any, category: str, label: str, **extra: Any) -> dict[str, Any]:
    return {"key": key, "type": type_, "default": default, "category": category, "label": label, **extra}


def _on(key: str) -> dict[str, Any]:
    """visible_if condition: a bool setting is on."""
    return {"key": key, "eq": True}


def _cap(name: str, minimum: int | None = None) -> dict[str, Any]:
    """requires entry; only capabilities in LEGACY_CAPS mean anything here."""
    return {"cap": name} if minimum is None else {"cap": name, "min": minimum}


LEGACY_CAPS = frozenset({"relays", "inputs", "buttons", "proximity", "power_button", "speaker"})
"""Capabilities the legacy client derives from the model; any other one is unknown."""

SCREENSAVER_OPTIONS = [
    {"value": 0, "label": "Off"},
    {"value": 1, "label": "Clock"},
    {"value": 2, "label": "Clock and date"},
    {"value": 3, "label": "Always-on display"},
]
SCREENSAVER_AOD = 3
SW_INPUT_MODES = [
    {"value": 0, "label": "Detached"},
    {"value": 1, "label": "Button"},
    {"value": 2, "label": "Switch (toggle on edge)"},
    {"value": 3, "label": "Switch (follow)"},
]
SW_INPUT_DETACHED = 0

_WEBVIEW = [{"key": "liteMode", "eq": False}]
_SCREENSAVER = [_on("screenSaver")]
_MQTT = [_on("mqttEnabled")]
_VOICE = [_on("voiceAssistantEnabled")]
_WAKE = [_on("voiceWakeEnabled")]
_TEMP_OFFSET = [_on("dynamicTempOffsetEnabled")]

LEGACY_SCHEMA: list[dict[str, Any]] = [
    # general / webview
    _s("webviewUrl", "string", "", "general", "Dashboard URL", visible_if=_WEBVIEW),
    _s("ignoreSslErrors", "bool", False, "general", "Ignore SSL errors", visible_if=_WEBVIEW),
    _s("liteMode", "bool", False, "general", "Lite mode (no WebView)"),
    _s("extendedJavascriptInterface", "bool", False, "advanced", "Extended JavaScript interface", visible_if=_WEBVIEW),
    _s("httpServer", "bool", True, "advanced", "Legacy HTTP server"),
    _s("adbWifiEnabled", "bool", False, "advanced", "ADB over Wi-Fi"),
    _s("mediaEnabled", "bool", False, "media", "Media playback", requires=[_cap("speaker")]),
    # display
    _s("automaticBrightness", "bool", True, "display", "Automatic brightness"),
    _s(
        "brightness",
        "int",
        255,
        "display",
        "Brightness",
        min=0,
        max=255,
        visible_if=[{"key": "automaticBrightness", "eq": False}],
    ),
    _s(
        "minBrightness",
        "int",
        48,
        "display",
        "Minimum brightness",
        min=0,
        max=255,
        visible_if=[_on("automaticBrightness")],
    ),
    _s("nightModeEnabled", "bool", False, "display", "Night mode"),
    # screensaver
    _s("screenSaver", "bool", True, "screensaver", "Screensaver"),
    _s(
        "screenSaverDelay",
        "int",
        45,
        "screensaver",
        "Screensaver delay",
        min=5,
        max=3600,
        unit="s",
        visible_if=_SCREENSAVER,
    ),
    _s(
        "screenSaverId",
        "enum",
        0,
        "screensaver",
        "Screensaver type",
        options=SCREENSAVER_OPTIONS,
        visible_if=_SCREENSAVER,
    ),
    _s(
        "screenSaverMinBrightness",
        "int",
        0,
        "screensaver",
        "Screensaver brightness",
        min=0,
        max=255,
        # the always-on display keeps its own brightness
        visible_if=[*_SCREENSAVER, {"key": "screenSaverId", "ne": SCREENSAVER_AOD}],
    ),
    _s(
        "wakeOnProximity",
        "bool",
        False,
        "screensaver",
        "Wake on proximity",
        visible_if=_SCREENSAVER,
        requires=[_cap("proximity")],
    ),
    _s(
        "proximityKeepAwakeSeconds",
        "int",
        30,
        "screensaver",
        "Keep awake after proximity",
        min=0,
        max=3600,
        unit="s",
        visible_if=_SCREENSAVER,
        requires=[_cap("proximity")],
    ),
    _s("touchToWake", "bool", True, "screensaver", "Touch to wake"),
    _s("sleepOptimizationLevel", "int", 0, "screensaver", "Sleep optimization level", min=0, max=2),
    # inputs
    _s("switchOnSwipe", "bool", False, "inputs", "Toggle relay on swipe", requires=[_cap("relays", 1)]),
    _s("publishSwipeEvents", "bool", True, "inputs", "Publish swipe events"),
    _s("powerButtonAutoReboot", "bool", False, "inputs", "Power button reboots", requires=[_cap("power_button")]),
    _s(
        "buttonRelayEnabled",
        "bool",
        False,
        "inputs",
        "Buttons switch relays",
        requires=[_cap("buttons", 1), _cap("relays", 1)],
    ),
    *[
        _s(
            f"buttonRelayMap{i}",
            "int",
            -1,
            "inputs",
            f"Button {i + 1} relay",
            min=-1,
            max=1,
            visible_if=[_on("buttonRelayEnabled")],
            requires=[_cap("buttons", i + 1), _cap("relays", 1)],
        )
        for i in range(4)
    ],
    _s("swInputMode0", "enum", 1, "inputs", "Input 1 mode", options=SW_INPUT_MODES, requires=[_cap("inputs", 1)]),
    _s(
        "swInputRelayMap0",
        "int",
        0,
        "inputs",
        "Input 1 relay",
        min=-1,
        max=1,
        visible_if=[{"key": "swInputMode0", "ne": SW_INPUT_DETACHED}],
        requires=[_cap("inputs", 1), _cap("relays", 1)],
    ),
    _s("swInputInvert0", "bool", False, "inputs", "Invert input 1", requires=[_cap("inputs", 1)]),
    # mqtt
    _s("mqttEnabled", "bool", False, "mqtt", "MQTT"),
    _s("mqttBroker", "string", "", "mqtt", "MQTT broker", visible_if=_MQTT),
    _s("mqttPort", "int", 1883, "mqtt", "MQTT port", min=1, max=65535, visible_if=_MQTT),
    _s("mqttUsername", "string", "", "mqtt", "MQTT username", visible_if=_MQTT),
    _s("mqttPassword", "string", "", "mqtt", "MQTT password", secret=True, visible_if=_MQTT),
    _s("mqttDeviceId", "string", "", "mqtt", "MQTT device id", per_device=True, visible_if=_MQTT),
    _s("mqttHomeAssistantDiscovery", "bool", True, "mqtt", "MQTT Home Assistant discovery", visible_if=_MQTT),
    _s("mqttRetainState", "bool", True, "mqtt", "Retain MQTT state", visible_if=_MQTT),
    # voice
    _s("voiceAssistantEnabled", "bool", False, "voice", "Voice assistant (own Home Assistant token)"),
    _s("voiceAssistantToken", "string", "", "voice", "Home Assistant token", secret=True, visible_if=_VOICE),
    _s("voiceAssistantPipelineId", "string", "", "voice", "Assist pipeline id", visible_if=_VOICE),
    _s(
        "voiceAssistantMaxRecordSeconds",
        "int",
        10,
        "voice",
        "Max recording",
        min=1,
        max=60,
        unit="s",
        visible_if=_VOICE,
    ),
    _s("voiceAssistantMuted", "bool", False, "voice", "Microphone muted", visible_if=_VOICE),
    _s("voiceWakeEnabled", "bool", False, "voice", "Wake word", visible_if=_VOICE),
    _s("voiceWakeModelName", "string", "okay_nabu", "voice", "Wake word model", visible_if=_WAKE),
    _s(
        "voiceWakeSensitivity",
        "float",
        0.5,
        "voice",
        "Wake word sensitivity",
        min=0,
        max=1,
        step=0.05,
        visible_if=_WAKE,
    ),
    _s("voiceWakeCooldownSec", "int", 3, "voice", "Wake word cooldown", min=0, max=60, unit="s", visible_if=_WAKE),
    _s("voiceWakeSoundEnabled", "bool", True, "voice", "Wake sound", visible_if=_WAKE),
    _s("voiceScoreBarEnabled", "bool", False, "voice", "Show wake score bar", visible_if=_WAKE),
    _s("voiceWakeExperimentalModels", "bool", False, "voice", "Experimental wake words", visible_if=_WAKE),
    # bluetooth
    _s("bluetoothProxyEnabled", "bool", False, "bluetooth", "Bluetooth proxy (ESPHome emulation)"),
    _s(
        "bluetoothProxyName",
        "string",
        "ShellyElevate",
        "bluetooth",
        "Bluetooth proxy name",
        per_device=True,
        visible_if=[_on("bluetoothProxyEnabled")],
    ),
    # temperature
    _s("publishThermalSensors", "bool", False, "advanced", "Publish thermal sensors"),
    _s("dynamicTempOffsetEnabled", "bool", False, "advanced", "Dynamic temperature offset"),
    _s("dynamicTempOffsetZone", "string", "", "advanced", "Thermal zone for offset", visible_if=_TEMP_OFFSET),
    _s("dynamicTempOffsetBaseline", "float", 0, "advanced", "Offset baseline", visible_if=_TEMP_OFFSET),
    _s("dynamicTempOffsetK", "float", 0, "advanced", "Offset factor", visible_if=_TEMP_OFFSET),
    # internal
    _s("settingEverShown", "bool", False, "advanced", "Settings shown once", per_device=True, hidden=True),
]
