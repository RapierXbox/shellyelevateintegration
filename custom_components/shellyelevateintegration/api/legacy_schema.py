"""Settings schema for the legacy app (which has no schema endpoint).

Mirrors Constants.java / the Configuration-Reference wiki page of ShellyElevate.
"""

from __future__ import annotations

from typing import Any


def _s(key: str, type_: str, default: Any, category: str, label: str, **extra: Any) -> dict[str, Any]:
    return {"key": key, "type": type_, "default": default, "category": category, "label": label, **extra}


SCREENSAVER_OPTIONS = [
    {"value": 0, "label": "Off"},
    {"value": 1, "label": "Clock"},
    {"value": 2, "label": "Clock and date"},
    {"value": 3, "label": "Always-on display"},
]
SW_INPUT_MODES = [
    {"value": 0, "label": "Detached"},
    {"value": 1, "label": "Button"},
    {"value": 2, "label": "Switch (toggle on edge)"},
    {"value": 3, "label": "Switch (follow)"},
]

LEGACY_SCHEMA: list[dict[str, Any]] = [
    # general / webview
    _s("webviewUrl", "string", "", "general", "Dashboard URL"),
    _s("ignoreSslErrors", "bool", False, "general", "Ignore SSL errors"),
    _s("liteMode", "bool", False, "general", "Lite mode (no WebView)"),
    _s("extendedJavascriptInterface", "bool", False, "advanced", "Extended JavaScript interface"),
    _s("httpServer", "bool", True, "advanced", "Legacy HTTP server"),
    _s("adbWifiEnabled", "bool", False, "advanced", "ADB over Wi-Fi"),
    _s("mediaEnabled", "bool", False, "media", "Media playback"),
    # display
    _s("automaticBrightness", "bool", True, "display", "Automatic brightness"),
    _s("brightness", "int", 255, "display", "Brightness", min=0, max=255),
    _s("minBrightness", "int", 48, "display", "Minimum brightness", min=0, max=255),
    _s("nightModeEnabled", "bool", False, "display", "Night mode"),
    # screensaver
    _s("screenSaver", "bool", True, "screensaver", "Screensaver"),
    _s("screenSaverDelay", "int", 45, "screensaver", "Screensaver delay", min=5, max=3600, unit="s"),
    _s("screenSaverId", "enum", 0, "screensaver", "Screensaver type", options=SCREENSAVER_OPTIONS),
    _s("screenSaverMinBrightness", "int", 0, "screensaver", "Screensaver brightness", min=0, max=255),
    _s("wakeOnProximity", "bool", False, "screensaver", "Wake on proximity"),
    _s("proximityKeepAwakeSeconds", "int", 30, "screensaver", "Keep awake after proximity", min=0, max=3600, unit="s"),
    _s("touchToWake", "bool", True, "screensaver", "Touch to wake"),
    _s("sleepOptimizationLevel", "int", 0, "screensaver", "Sleep optimization level", min=0, max=2),
    # inputs
    _s("switchOnSwipe", "bool", False, "inputs", "Toggle relay on swipe"),
    _s("publishSwipeEvents", "bool", True, "inputs", "Publish swipe events"),
    _s("powerButtonAutoReboot", "bool", False, "inputs", "Power button reboots"),
    _s("buttonRelayEnabled", "bool", False, "inputs", "Buttons switch relays"),
    *[_s(f"buttonRelayMap{i}", "int", -1, "inputs", f"Button {i + 1} relay", min=-1, max=1) for i in range(4)],
    _s("swInputMode0", "enum", 1, "inputs", "Input 1 mode", options=SW_INPUT_MODES),
    _s("swInputRelayMap0", "int", 0, "inputs", "Input 1 relay", min=-1, max=1),
    _s("swInputInvert0", "bool", False, "inputs", "Invert input 1"),
    # mqtt
    _s("mqttEnabled", "bool", False, "mqtt", "MQTT"),
    _s("mqttBroker", "string", "", "mqtt", "MQTT broker"),
    _s("mqttPort", "int", 1883, "mqtt", "MQTT port", min=1, max=65535),
    _s("mqttUsername", "string", "", "mqtt", "MQTT username"),
    _s("mqttPassword", "string", "", "mqtt", "MQTT password", secret=True),
    _s("mqttDeviceId", "string", "", "mqtt", "MQTT device id", per_device=True),
    _s("mqttHomeAssistantDiscovery", "bool", True, "mqtt", "MQTT Home Assistant discovery"),
    _s("mqttRetainState", "bool", True, "mqtt", "Retain MQTT state"),
    # voice
    _s("voiceAssistantEnabled", "bool", False, "voice", "Voice assistant (own Home Assistant token)"),
    _s("voiceAssistantToken", "string", "", "voice", "Home Assistant token", secret=True),
    _s("voiceAssistantPipelineId", "string", "", "voice", "Assist pipeline id"),
    _s("voiceAssistantMaxRecordSeconds", "int", 10, "voice", "Max recording", min=1, max=60, unit="s"),
    _s("voiceAssistantMuted", "bool", False, "voice", "Microphone muted"),
    _s("voiceWakeEnabled", "bool", False, "voice", "Wake word"),
    _s("voiceWakeModelName", "string", "okay_nabu", "voice", "Wake word model"),
    _s("voiceWakeSensitivity", "float", 0.5, "voice", "Wake word sensitivity", min=0, max=1, step=0.05),
    _s("voiceWakeCooldownSec", "int", 3, "voice", "Wake word cooldown", min=0, max=60, unit="s"),
    _s("voiceWakeSoundEnabled", "bool", True, "voice", "Wake sound"),
    _s("voiceScoreBarEnabled", "bool", False, "voice", "Show wake score bar"),
    _s("voiceWakeExperimentalModels", "bool", False, "voice", "Experimental wake words"),
    # bluetooth
    _s("bluetoothProxyEnabled", "bool", False, "bluetooth", "Bluetooth proxy (ESPHome emulation)"),
    _s("bluetoothProxyName", "string", "ShellyElevate", "bluetooth", "Bluetooth proxy name", per_device=True),
    # temperature
    _s("publishThermalSensors", "bool", False, "advanced", "Publish thermal sensors"),
    _s("dynamicTempOffsetEnabled", "bool", False, "advanced", "Dynamic temperature offset"),
    _s("dynamicTempOffsetZone", "string", "", "advanced", "Thermal zone for offset"),
    _s("dynamicTempOffsetBaseline", "float", 0, "advanced", "Offset baseline"),
    _s("dynamicTempOffsetK", "float", 0, "advanced", "Offset factor"),
    # internal
    _s("settingEverShown", "bool", False, "advanced", "Settings shown once", per_device=True),
]
