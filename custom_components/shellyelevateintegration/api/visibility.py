"""Which settings can take effect right now (`visible_if`, `requires` and `hidden` of the schema).

Implements the evaluation rule of protocol v1 section 4 like the app (SettingVisibility.java), plus the
`known_caps` of the panel (frontend/src/visibility.ts) for displays that do not report every capability.
Pure functions without Home Assistant imports.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from enum import Enum
from typing import Any, TypeGuard

from .models import SettingDef


class SettingState(Enum):
    """State of a setting as the protocol defines it."""

    VISIBLE = "visible"
    UNAVAILABLE = "unavailable"
    """A `requires` entry fails: the hardware or feature is missing."""
    INACTIVE = "inactive"
    """A `visible_if` condition fails or refers to a setting that is not shown itself."""


def _is_number(value: Any) -> TypeGuard[int | float]:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _js_str(value: Any) -> str:
    """String form like JavaScript String() so "true" matches True for legacy displays."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def same_value(a: Any, b: Any, *, loose: bool = False) -> bool:
    """Whether two setting values are equal like the app compares them.

    Numbers compare by value (1 equals 1.0) but true is not 1 and "1" is not 1. `loose` also
    matches the string form ("true" equals True) for legacy displays, which may report strings.
    """
    if _is_number(a) and _is_number(b):
        return float(a) == float(b)
    if isinstance(a, bool) != isinstance(b, bool) and (_is_number(a) or _is_number(b)):
        # true is not 1
        return False
    if type(a) is type(b) or a is None or b is None:
        return bool(a == b)
    # legacy displays may report a value as a string
    return loose and _js_str(a) == _js_str(b)


def condition_holds(cond: Mapping[str, Any], value: Any, *, loose: bool = False) -> bool:
    """Whether one `visible_if` condition holds for `value`; an unknown operator fails like in the app."""
    if "eq" in cond:
        return same_value(value, cond["eq"], loose=loose)
    if "ne" in cond:
        return not same_value(value, cond["ne"], loose=loose)
    if isinstance(cond.get("in"), list):
        return any(same_value(value, allowed, loose=loose) for allowed in cond["in"])
    return False


def requirement_met(req: Mapping[str, Any], caps: Mapping[str, Any], known_caps: Collection[str] | None) -> bool:
    """Whether one `requires` entry holds; a capability outside `known_caps` counts as met."""
    cap = req.get("cap")
    if known_caps is not None and cap not in known_caps:
        # legacy displays do not report every capability
        return True
    value = caps.get(cap) if isinstance(cap, str) else None
    minimum = req.get("min")
    if minimum is not None:
        return _is_number(value) and _is_number(minimum) and value >= minimum
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if _is_number(value):
        return value != 0
    if isinstance(value, str):
        return value != ""
    return True


def fallback_value(item: SettingDef) -> Any:
    """Stand-in value of an unavailable setting: false for a bool and its default otherwise."""
    return False if item.type == "bool" else item.default


class VisibilityEvaluator:
    """Evaluates the visibility of settings against current values and capabilities."""

    def __init__(
        self,
        schema: Iterable[SettingDef],
        values: Mapping[str, Any],
        caps: Mapping[str, Any],
        known_caps: Collection[str] | None = None,
        *,
        loose: bool = False,
    ) -> None:
        """Initialize; `known_caps` None means every capability is known, `loose` see same_value."""
        self._defs = {item.key: item for item in schema}
        self._values = values
        self._caps = caps
        self._known = known_caps
        self._loose = loose

    def definition(self, key: str) -> SettingDef | None:
        """Definition of a setting."""
        return self._defs.get(key)

    def visible(self, key: str) -> bool:
        """Whether a UI shows the setting: it is known, not hidden and visible."""
        item = self._defs.get(key)
        if item is None or item.hidden:
            return False
        return self._state(item, set(), None) is SettingState.VISIBLE

    def visible_on(self, key: str, stable_keys: Collection[str]) -> bool:
        """Like visible but only conditions on `stable_keys` are compared with their values.

        A condition on any other key holds as long as that setting is shown itself, so a value that
        changes as a side effect of a command cannot change the result.
        """
        item = self._defs.get(key)
        if item is None or item.hidden:
            return False
        return self._state(item, set(), stable_keys) is SettingState.VISIBLE

    def state(self, key: str) -> SettingState | None:
        """State of a setting (ignoring `hidden`), None if the schema does not have it."""
        item = self._defs.get(key)
        return None if item is None else self._state(item, set(), None)

    def value(self, key: str) -> Any:
        """Current value of a setting, its default when unset."""
        value = self._values.get(key)
        if value is None and (item := self._defs.get(key)) is not None:
            return item.default
        return value

    def _state(self, item: SettingDef, visiting: set[str], stable: Collection[str] | None) -> SettingState:
        if not all(requirement_met(req, self._caps, self._known) for req in item.requires or ()):
            return SettingState.UNAVAILABLE
        if not item.visible_if:
            return SettingState.VISIBLE
        if item.key in visiting:
            # a cycle never resolves so every setting on it stays hidden
            return SettingState.INACTIVE
        visiting.add(item.key)
        try:
            for cond in item.visible_if:
                parent = self._defs.get(cond.get("key"))  # type: ignore[arg-type]
                if parent is None:
                    return SettingState.INACTIVE
                parent_state = self._state(parent, visiting, stable)
                if parent_state is SettingState.INACTIVE:
                    return SettingState.INACTIVE
                if parent_state is SettingState.VISIBLE and stable is not None and parent.key not in stable:
                    continue
                # a parent the display lacks counts as off so a setting that replaces it still shows
                value = fallback_value(parent) if parent_state is SettingState.UNAVAILABLE else self.value(parent.key)
                if not condition_holds(cond, value, loose=self._loose):
                    return SettingState.INACTIVE
            return SettingState.VISIBLE
        finally:
            visiting.discard(item.key)


def setting_visible(
    key: str,
    schema: Iterable[SettingDef],
    values: Mapping[str, Any],
    caps: Mapping[str, Any],
    known_caps: Collection[str] | None = None,
) -> bool:
    """Whether a UI shows `key` (see VisibilityEvaluator)."""
    return VisibilityEvaluator(schema, values, caps, known_caps).visible(key)
