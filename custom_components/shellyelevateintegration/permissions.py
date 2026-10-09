"""Grant the app's permissions over ADB when the display reports them missing.

The installer grants them once, but displays installed another way (or before a permission
was added) can miss the microphone or location permission. The display reports that in
`voice.error` and `ble.error`; with ADB this grants them again (at most once an hour, and
once after every app update), without ADB a repair issue explains what to do. So does the issue when
a grant went through but the display still reports the problem a while later.

WRITE_SECURE_SETTINGS (the ADB over Wi-Fi switch of the app) is not reported by the display, and an
update the app installed itself does not grant it. A read-only ADB check finds it after setup (at
most once an hour) and after the app version changed.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.util.hass_dict import HassKey

from .adb import steps
from .adb.manager import AdbError, PermissionGrant
from .const import DOMAIN
from .repairs import async_set_permissions_missing

if TYPE_CHECKING:
    from .device import ShellyElevateIntegrationDevice

_LOGGER = logging.getLogger(__name__)

AUTO_GRANT_INTERVAL = 3600
"""Seconds between automatic grants of one display."""
SETTLE_TIME = 60
"""Seconds the app gets after a grant (it restarts) before a problem it still reports is a repair issue."""

ERROR_KEYS = ("voice.error", "ble.error")

ADB_ONLY_PERMISSIONS = (steps.SECURE_SETTINGS_NAME,)
"""Permissions the display does not report missing: only the ADB check finds them."""


@dataclass(frozen=True, slots=True)
class _Grant:
    """The last finished automatic grant of a display."""

    finished: float
    """Monotonic time."""
    granted: bool
    """pm grant went through, so a problem the display still reports needs the user."""


_LAST_AUTO: HassKey[dict[str, _Grant]] = HassKey(f"{DOMAIN}_permission_grants")
"""entry_id -> last finished automatic grant (survives reloads; a cancelled one is not stored)."""

_LAST_CHECK: HassKey[dict[str, float]] = HassKey(f"{DOMAIN}_permission_checks")
"""entry_id -> monotonic time of the last read-only ADB check (survives reloads)."""


def permission_problems(state: dict[str, Any]) -> list[str]:
    """The display's own reasons that a grant can fix; empty when nothing is missing."""
    problems = []
    if isinstance(voice := state.get("voice.error"), str) and "permission" in voice:
        problems.append(voice)
    if isinstance(ble := state.get("ble.error"), str) and ("permission" in ble or "location" in ble):
        problems.append(ble)
    return problems


class PermissionGuard:
    """Watches a v1 display for missing permissions and grants them over ADB."""

    def __init__(self, device: ShellyElevateIntegrationDevice) -> None:
        """Initialize."""
        self.device = device
        self.hass: HomeAssistant = device.hass
        self._task: asyncio.Task[None] | None = None
        self._after_update = False
        self._unsubs: list[Callable[[], None]] = []
        self._settle: Callable[[], None] | None = None
        self._adb_missing: list[str] = []
        """ADB_ONLY_PERMISSIONS the last ADB check or grant found missing."""
        self._version: str | None = None

    @property
    def _title(self) -> str:
        return self.device.entry.title

    @callback
    def async_start(self) -> None:
        """Start watching the state (and check it right away)."""
        self._version = self.device.info.fw_version
        self._unsubs += [
            self.device.async_add_state_listener(self._on_state),
            self.device.async_add_availability_listener(self._on_availability),
            self.device.async_add_message_listener(self._on_message),
        ]
        self._evaluate()
        self._start_check()

    @callback
    def async_stop(self) -> None:
        """Stop watching."""
        if self._settle is not None:
            self._settle()
            self._settle = None
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    @callback
    def async_after_update(self) -> None:
        """Grant once after an app update (when the app is back)."""
        if self.device.adb is None:
            return
        if self.device.available:
            self._start("app update")
        else:
            self._after_update = True

    async def async_grant(self) -> PermissionGrant:
        """Grant now (button and repair); raises HomeAssistantError without ADB or on failure."""
        if self.device.adb is None:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="adb_disabled")
        result = await self.device.adb.async_grant_permissions()
        self._adb_missing = [name for name in result.missing if name in ADB_ONLY_PERMISSIONS]
        self._log(result)
        return result

    def problems(self) -> list[str]:
        """What is missing: the reasons the display reports and what the ADB check found."""
        return [*permission_problems(self.device.state), *self._adb_missing]

    @callback
    def _on_state(self, changes: dict[str, Any]) -> None:
        if any(key in changes for key in ERROR_KEYS):
            self._evaluate()

    @callback
    def _on_message(self, message: dict[str, Any]) -> None:
        if message.get("type") != "_info_changed":
            return
        if (version := self.device.info.fw_version) != self._version:
            # the app may have updated itself so the new version may request more
            self._version = version
            self.async_after_update()

    @callback
    def _on_availability(self) -> None:
        if not self.device.available:
            return
        if self._after_update:
            self._after_update = False
            self._start("app update")
        self._evaluate()

    @callback
    def _evaluate(self) -> None:
        problems = self.problems()
        if not problems:
            async_set_permissions_missing(self.hass, self.device, None)
            return
        if self.device.adb is None:
            async_set_permissions_missing(self.hass, self.device, problems)
            return
        if self._task is not None and not self._task.done():
            return
        last = self.hass.data.get(_LAST_AUTO, {}).get(self.device.entry.entry_id)
        if last is not None and (since := time.monotonic() - last.finished) < AUTO_GRANT_INTERVAL:
            if last.granted and since >= SETTLE_TIME:
                # granted but still reported so another grant would not help either
                async_set_permissions_missing(self.hass, self.device, problems)
            return
        self._start(", ".join(problems))

    @callback
    def _start(self, reason: str) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = self.device.entry.async_create_background_task(
            self.hass, self._async_auto_grant(reason), f"{DOMAIN} grant permissions {self._title}"
        )

    @callback
    def _start_check(self) -> None:
        """Look for ADB_ONLY_PERMISSIONS in the background (at most once an hour)."""
        if self.device.adb is None or (self._task is not None and not self._task.done()):
            return
        checks = self.hass.data.setdefault(_LAST_CHECK, {})
        entry_id = self.device.entry.entry_id
        if (last := checks.get(entry_id)) is not None and time.monotonic() - last < AUTO_GRANT_INTERVAL:
            return
        checks[entry_id] = time.monotonic()
        self._task = self.device.entry.async_create_background_task(
            self.hass, self._async_check(), f"{DOMAIN} check permissions {self._title}"
        )

    async def _async_check(self) -> None:
        assert self.device.adb is not None
        try:
            missing = await self.device.adb.async_missing_permissions()
        except HomeAssistantError as err:
            _LOGGER.debug("%s: could not check the app permissions over ADB: %s", self._title, err)
            return
        if adb_only := [name for name in missing if name in ADB_ONLY_PERMISSIONS]:
            await self._async_auto_grant(", ".join(adb_only))

    async def _async_auto_grant(self, reason: str) -> None:
        _LOGGER.debug("%s: granting the app permissions over ADB (%s)", self._title, reason)
        try:
            result = await self.async_grant()
        except HomeAssistantError as err:
            # stored only once it finished so a grant cancelled by a reload runs again
            self._finished(granted=False)
            log = _LOGGER.warning if isinstance(err, AdbError) else _LOGGER.debug
            log("%s: could not grant the app permissions over ADB: %s", self._title, err)
            if problems := self.problems():
                async_set_permissions_missing(self.hass, self.device, problems)
            return
        self._finished(granted=not result.missing)
        if result.missing and (problems := self.problems()):
            # pm grant was refused: only the user can help
            async_set_permissions_missing(self.hass, self.device, problems)
            return
        # look again once the app restarted with the permissions
        if self._settle is not None:
            self._settle()
        self._settle = async_call_later(self.hass, SETTLE_TIME, self._on_settled)

    @callback
    def _finished(self, *, granted: bool) -> None:
        self.hass.data.setdefault(_LAST_AUTO, {})[self.device.entry.entry_id] = _Grant(time.monotonic(), granted)

    @callback
    def _on_settled(self, _now: Any) -> None:
        self._settle = None
        self._evaluate()

    @callback
    def _log(self, result: PermissionGrant) -> None:
        if result.granted:
            _LOGGER.info(
                "%s: granted %s over ADB%s",
                self._title,
                ", ".join(result.granted),
                " and restarted the app" if result.restarted else "",
            )
        else:
            _LOGGER.debug("%s: no app permission was missing", self._title)
        if result.missing:
            _LOGGER.warning("%s: still missing after granting over ADB: %s", self._title, ", ".join(result.missing))
        if result.failed:
            _LOGGER.debug("%s: permission steps that failed: %s", self._title, ", ".join(result.failed))
