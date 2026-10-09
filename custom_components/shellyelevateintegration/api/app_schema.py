"""Visibility rules of the current app (SettingsRegistry.java) for v1 displays that send none.

App versions before the rules were added send a schema without `visible_if`, `requires`, `hidden` and
`read_only`, so every setting would show. Their keys mean the same, so the rules of the current app
are filled in.
"""

from __future__ import annotations

from typing import Any

from .models import SettingDef


def _r(key: str, type_: str, default: Any, **rules: Any) -> dict[str, Any]:
    return {"key": key, "type": type_, "default": default, **rules}


def _eq(key: str, value: Any) -> dict[str, Any]:
    return {"key": key, "eq": value}


def _cap(name: str, minimum: int | None = None) -> dict[str, Any]:
    return {"cap": name} if minimum is None else {"cap": name, "min": minimum}


_WEBVIEW = [_eq("displayModule", "webview")]
_APP = [_eq("displayModule", "app")]
_SAVER = _eq("screenSaver", True)
_MQTT = [_eq("mqttEnabled", True)]
_VOICE = _eq("haVoiceEnabled", True)
_WAKE = _eq("voiceWakeEnabled", True)
_OFFSET = [_eq("dynamicTempOffsetEnabled", True)]
_TEMPERATURE = [_cap("temperature")]

APP_RULES: list[dict[str, Any]] = [
    # general and screen content
    _r("displayModule", "enum", "webview"),
    _r("webviewUrl", "string", "", visible_if=_WEBVIEW),
    _r("ignoreSslErrors", "bool", False, visible_if=_WEBVIEW),
    _r("extendedJavascriptInterface", "bool", False, visible_if=_WEBVIEW),
    _r("webview.modernFrontend", "bool", False, visible_if=_WEBVIEW),
    _r("webview.reduceMotion", "bool", False, visible_if=_WEBVIEW),
    _r("app.package", "string", "", visible_if=_APP),
    _r("app.component", "string", "", visible_if=_APP, read_only=True),
    _r("app.keepInFront", "bool", True, visible_if=_APP),
    _r("liteMode", "bool", False),
    _r("appSwitcherGesture", "enum", "swipe_2_up"),
    _r("appSwitcherPreviews", "bool", True, visible_if=[{"key": "appSwitcherGesture", "ne": "off"}]),
    _r("settingEverShown", "bool", False, hidden=True),
    # display
    _r("automaticBrightness", "bool", True, requires=[_cap("lux")]),
    _r("brightness", "int", 255, visible_if=[_eq("automaticBrightness", False)]),
    _r("minBrightness", "int", 48, visible_if=[_eq("automaticBrightness", True)], requires=[_cap("lux")]),
    _r("nightModeEnabled", "bool", False),
    # screensaver
    _r("screenSaver", "bool", True),
    _r("screenSaverDelay", "int", 45, visible_if=[_SAVER]),
    _r("screenSaverId", "enum", 0, visible_if=[_SAVER]),
    _r(
        "screenSaverMinBrightness",
        "int",
        48,
        visible_if=[_SAVER, {"key": "screenSaverId", "in": [1, 2]}, _eq("automaticBrightness", True)],
        requires=[_cap("lux")],
    ),
    _r("wakeOnProximity", "bool", True, visible_if=[_SAVER], requires=[_cap("proximity")]),
    _r(
        "proximityKeepAwakeSeconds",
        "int",
        30,
        visible_if=[_SAVER, _eq("wakeOnProximity", True)],
        requires=[_cap("proximity")],
    ),
    _r("touchToWake", "bool", True, visible_if=[_SAVER]),
    _r("sleepOptimizationLevel", "enum", 0, visible_if=[_SAVER]),
    # inputs
    _r("switchOnSwipe", "bool", True, requires=[_cap("relays", 1)]),
    _r("publishSwipeEvents", "bool", True),
    _r("powerButtonAutoReboot", "bool", True, requires=[_cap("power_button")]),
    _r("buttonRelayEnabled", "bool", False, requires=[_cap("buttons", 1), _cap("relays", 1)]),
    *[
        _r(
            f"buttonRelayMap{i}",
            "int",
            -1,
            visible_if=[_eq("buttonRelayEnabled", True)],
            requires=[_cap("buttons", i + 1), _cap("relays", 1)],
        )
        for i in range(4)
    ],
    _r("swInputMode0", "enum", 1, requires=[_cap("inputs", 1)]),
    _r(
        "swInputRelayMap0",
        "int",
        0,
        visible_if=[{"key": "swInputMode0", "ne": 0}],
        requires=[_cap("inputs", 1), _cap("relays", 1)],
    ),
    _r("swInputInvert0", "bool", False, requires=[_cap("inputs", 1)]),
    # mqtt
    _r("mqttEnabled", "bool", False),
    _r("mqttBroker", "string", "", visible_if=_MQTT),
    _r("mqttPort", "int", 1883, visible_if=_MQTT),
    _r("mqttUsername", "string", "", visible_if=_MQTT),
    _r("mqttPassword", "string", "", visible_if=_MQTT),
    _r("mqttDeviceId", "string", "", visible_if=_MQTT),
    _r("mqttHomeAssistantDiscovery", "bool", True, visible_if=_MQTT),
    _r("mqttRetainState", "bool", True, visible_if=_MQTT),
    # voice
    _r(
        "haVoiceEnabled",
        "bool",
        False,
        visible_if=[_eq("integrationApiEnabled", True)],
        requires=[_cap("microphone")],
    ),
    _r("voiceAssistantMaxRecordSeconds", "int", 10, visible_if=[_VOICE]),
    _r("voiceAssistantMuted", "bool", False, visible_if=[_VOICE]),
    _r("voiceWakeEnabled", "bool", True, visible_if=[_VOICE]),
    _r("voiceWakeModelName", "string", "", visible_if=[_VOICE, _WAKE]),
    _r("voiceWakeSensitivity", "int", 50, visible_if=[_VOICE, _WAKE]),
    _r("voiceWakeCooldownSec", "int", 5, visible_if=[_VOICE, _WAKE]),
    _r("voiceWakeSoundEnabled", "bool", True, visible_if=[_VOICE]),
    _r("voiceScoreBarEnabled", "bool", False, visible_if=[_VOICE, _WAKE]),
    _r("voiceWakeExperimentalModels", "bool", False, visible_if=[_VOICE, _WAKE]),
    # bluetooth and media
    _r(
        "bleScannerEnabled",
        "bool",
        False,
        visible_if=[_eq("integrationApiEnabled", True)],
        requires=[_cap("bluetooth")],
    ),
    _r("mediaEnabled", "bool", False),
    # advanced
    _r("integrationApiEnabled", "bool", True),
    _r("httpServer", "bool", True),
    _r("adbWifiEnabled", "bool", False),
    _r("updatePrerelease", "bool", False),
    _r("publishThermalSensors", "bool", False, visible_if=_MQTT),
    _r("dynamicTempOffsetEnabled", "bool", False, requires=_TEMPERATURE),
    _r("dynamicTempOffsetZone", "string", "", visible_if=_OFFSET, requires=_TEMPERATURE),
    _r("dynamicTempOffsetBaseline", "float", 40.0, visible_if=_OFFSET, requires=_TEMPERATURE),
    _r("dynamicTempOffsetK", "float", 0.3, visible_if=_OFFSET, requires=_TEMPERATURE),
]

_BY_KEY = {rule["key"]: rule for rule in APP_RULES}


def _copy(rules: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [dict(rule) for rule in rules or ()]


def has_rules(schema: list[SettingDef]) -> bool:
    """Whether a schema carries visibility rules (older v1 apps send none)."""
    return any(item.visible_if or item.requires for item in schema)


def with_app_rules(schema: list[SettingDef]) -> list[SettingDef]:
    """Fill in the rules of the current app when a schema has none; otherwise return it unchanged."""
    if not schema or has_rules(schema):
        return schema
    keys = {item.key for item in schema}
    for item in schema:
        if (rule := _BY_KEY.get(item.key)) is None:
            continue
        # a condition on a key this app does not have would hide the setting for good
        item.visible_if = [cond for cond in _copy(rule.get("visible_if")) if cond["key"] in keys] or None
        item.requires = _copy(rule.get("requires")) or None
        item.hidden = item.hidden or bool(rule.get("hidden"))
        item.read_only = item.read_only or bool(rule.get("read_only"))
    return schema


def app_schema(keys: set[str], *, undescribed: bool = True) -> list[SettingDef]:
    """Definitions with the rules of the current app for the given keys (when no schema could be read).

    `undescribed` adds a plain string definition for each key the current app does not have either.
    """
    defs = [
        SettingDef(key=rule["key"], type=rule["type"], default=rule["default"])
        for rule in APP_RULES
        if rule["key"] in keys
    ]
    if undescribed:
        defs += [SettingDef(key=key, type="string") for key in sorted(keys - set(_BY_KEY))]
    return with_app_rules(defs)
