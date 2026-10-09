"""Visibility rules of settings (protocol v1 section 4) and the built-in app rules."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.shellyelevateintegration.api.app_schema import (
    APP_RULES,
    app_schema,
    has_rules,
    with_app_rules,
)
from custom_components.shellyelevateintegration.api.models import SettingDef
from custom_components.shellyelevateintegration.api.visibility import (
    SettingState,
    VisibilityEvaluator,
    condition_holds,
    fallback_value,
    requirement_met,
    same_value,
    setting_visible,
)


def _defs(*items: dict[str, Any]) -> list[SettingDef]:
    return [SettingDef.from_dict({"type": "bool", **item}) for item in items]


@pytest.mark.parametrize(
    ("a", "b", "loose", "expected"),
    [
        (1, 1.0, False, True),
        (True, 1, False, False),
        (1, True, True, False),
        ("1", 1, False, False),
        ("true", True, False, False),
        ("true", True, True, True),
        ("2", 2.0, True, True),
        (None, None, False, True),
        (None, 0, False, False),
        ("a", "a", False, True),
        ("false", False, True, True),
        ([1], "x", True, False),
    ],
)
def test_same_value(a: Any, b: Any, loose: bool, expected: bool) -> None:
    """Numbers by value, true is not 1, strings only loosely."""
    assert same_value(a, b, loose=loose) is expected


@pytest.mark.parametrize(
    ("cond", "value", "expected"),
    [
        ({"eq": "webview"}, "webview", True),
        ({"eq": "webview"}, "app", False),
        ({"ne": "off"}, "swipe_2_up", True),
        ({"ne": "off"}, "off", False),
        ({"in": [1, 2]}, 2, True),
        ({"in": [1, 2]}, 3, False),
        ({"in": "not a list"}, 1, False),
        ({"gt": 1}, 5, False),
    ],
)
def test_condition_holds(cond: dict[str, Any], value: Any, expected: bool) -> None:
    """eq, ne and in; an unknown operator fails like in the app."""
    assert condition_holds(cond, value) is expected


@pytest.mark.parametrize(
    ("req", "caps", "known", "expected"),
    [
        ({"cap": "lux"}, {"lux": True}, None, True),
        ({"cap": "lux"}, {"lux": False}, None, False),
        ({"cap": "lux"}, {}, None, False),
        ({"cap": "lux"}, {}, {"relays"}, True),
        ({"cap": "relays", "min": 2}, {"relays": 2}, None, True),
        ({"cap": "relays", "min": 2}, {"relays": 1}, None, False),
        ({"cap": "relays", "min": 1}, {"relays": True}, None, False),
        ({"cap": "relays"}, {"relays": 0}, None, False),
        ({"cap": "relays"}, {"relays": 2}, None, True),
        ({"cap": "name"}, {"name": ""}, None, False),
        ({"cap": "name"}, {"name": "x"}, None, True),
        ({"cap": "list"}, {"list": [1]}, None, True),
        ({"cap": 5}, {}, None, False),
    ],
)
def test_requirement_met(req: dict[str, Any], caps: dict[str, Any], known: set[str] | None, expected: bool) -> None:
    """Truthy capabilities, minimums and unknown capabilities."""
    assert requirement_met(req, caps, known) is expected


def test_fallback_value() -> None:
    """An unavailable bool counts as off, anything else as its default."""
    assert fallback_value(SettingDef(key="a", type="bool", default=True)) is False
    assert fallback_value(SettingDef(key="a", type="int", default=3)) == 3


def test_evaluator() -> None:
    """Conditions, requirements, hidden settings, cycles and missing parents."""
    schema = _defs(
        {"key": "screenSaver", "default": True},
        {"key": "screenSaverDelay", "type": "int", "default": 45, "visible_if": [{"key": "screenSaver", "eq": True}]},
        {"key": "wake", "requires": [{"cap": "proximity"}], "visible_if": [{"key": "screenSaver", "eq": True}]},
        {"key": "keepAwake", "visible_if": [{"key": "wake", "eq": True}]},
        {"key": "replacement", "visible_if": [{"key": "wake", "eq": False}]},
        {"key": "hiddenOne", "hidden": True},
        {"key": "a", "visible_if": [{"key": "b", "eq": True}]},
        {"key": "b", "visible_if": [{"key": "a", "eq": True}]},
        {"key": "orphan", "visible_if": [{"key": "missing", "eq": True}]},
        {"key": "grandchild", "visible_if": [{"key": "screenSaverDelay", "ne": 0}]},
    )
    values = {"screenSaver": True, "wake": True, "keepAwake": True}
    evaluator = VisibilityEvaluator(schema, values, {"proximity": False})
    assert evaluator.visible("screenSaverDelay")
    assert evaluator.state("wake") is SettingState.UNAVAILABLE
    assert not evaluator.visible("wake")
    assert evaluator.state("keepAwake") is SettingState.INACTIVE  # parent unavailable counts as off
    assert evaluator.visible("replacement")
    assert not evaluator.visible("hiddenOne")
    assert evaluator.state("hiddenOne") is SettingState.VISIBLE
    assert not evaluator.visible("a") and not evaluator.visible("b")
    assert not evaluator.visible("orphan")
    assert not evaluator.visible("unknown")
    assert evaluator.state("unknown") is None
    assert evaluator.definition("screenSaver") is not None
    assert evaluator.value("screenSaverDelay") == 45  # unset: default
    assert evaluator.value("nothing") is None
    assert evaluator.visible("grandchild")

    off = VisibilityEvaluator(schema, {"screenSaver": False}, {"proximity": True})
    assert not off.visible("screenSaverDelay")
    assert off.state("grandchild") is SettingState.INACTIVE
    # only conditions on stable keys are compared with their values
    assert off.visible_on("screenSaverDelay", {"other"})
    assert not off.visible_on("screenSaverDelay", {"screenSaver"})
    assert not off.visible_on("hiddenOne", set())
    assert not off.visible_on("unknown", set())
    assert not off.visible_on("orphan", set())

    assert setting_visible("screenSaverDelay", schema, values, {})
    assert not setting_visible("wake", schema, values, {"proximity": False}, {"proximity"})


def test_loose_values() -> None:
    """Legacy displays report booleans as strings."""
    schema = _defs({"key": "liteMode"}, {"key": "webviewUrl", "visible_if": [{"key": "liteMode", "eq": False}]})
    assert VisibilityEvaluator(schema, {"liteMode": "false"}, {}, loose=True).visible("webviewUrl")
    assert not VisibilityEvaluator(schema, {"liteMode": "false"}, {}).visible("webviewUrl")


def test_with_app_rules() -> None:
    """Rules of the current app are filled in for an old schema without any."""
    schema = [
        SettingDef(key="screenSaver", type="bool"),
        SettingDef(key="screenSaverDelay", type="int"),
        SettingDef(key="screenSaverMinBrightness", type="int"),
        SettingDef(key="settingEverShown", type="bool"),
        SettingDef(key="app.component", type="string"),
        SettingDef(key="custom", type="string"),
    ]
    assert not has_rules(schema)
    result = with_app_rules(schema)
    by_key = {item.key: item for item in result}
    assert by_key["screenSaverDelay"].visible_if == [{"key": "screenSaver", "eq": True}]
    # conditions on keys this app does not have are dropped
    assert by_key["screenSaverMinBrightness"].visible_if == [{"key": "screenSaver", "eq": True}]
    assert by_key["screenSaverMinBrightness"].requires == [{"cap": "lux"}]
    assert by_key["settingEverShown"].hidden is True
    assert by_key["app.component"].read_only is True
    assert by_key["custom"].visible_if is None
    assert has_rules(result)
    # a schema with rules stays as it is
    assert with_app_rules(result) is result
    assert with_app_rules([]) == []


def test_app_schema() -> None:
    """Definitions for the keys a display has when no schema could be read."""
    defs = app_schema({"screenSaver", "screenSaverDelay", "custom"})
    assert [item.key for item in defs] == ["screenSaver", "screenSaverDelay", "custom"]
    assert defs[1].default == 45
    assert defs[2].type == "string"
    assert [item.key for item in app_schema({"custom"}, undescribed=False)] == []
    assert len({rule["key"] for rule in APP_RULES}) == len(APP_RULES)
