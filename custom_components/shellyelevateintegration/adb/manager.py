"""ADB access to a display (install, update, rescue, screenshots, logs)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
import io
import logging
import re
from typing import TYPE_CHECKING, Any

from adb_shell.adb_device_async import AdbDeviceAsync
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later

from ..const import DOMAIN, OPT_ADB, OPT_WATCHDOG, UPDATE_CHANNEL_STABLE
from ..repairs import async_set_app_down
from . import steps
from .apk import AppRelease, async_download_apk, async_latest_release
from .keys import AdbKey, async_get_adb_key
from .transport import create_device

if TYPE_CHECKING:
    from ..device import ShellyElevateIntegrationDevice

_LOGGER = logging.getLogger(__name__)

ProgressCallback = Callable[[str, dict[str, Any]], None]
"""Called with (step_id, details) while a long operation runs."""

WATCHDOG_DELAY = 120
WATCHDOG_MAX_DELAY = 1800
WATCHDOG_RESTARTS = 3
_BROADCAST_DATA = re.compile(r'Broadcast completed: result=-?\d+, data="([0-9a-fA-F]{64})"')


@dataclass(frozen=True, slots=True)
class PermissionGrant:
    """Result of AdbManager.async_grant_permissions."""

    granted: list[str]
    """Permissions (short names) and `location_mode` that were missing before and are not now."""
    missing: list[str]
    """Still missing afterwards."""
    failed: list[str]
    """Step ids whose command reported a failure."""
    restarted: bool


class AdbError(HomeAssistantError):
    """ADB operation failed."""


class _StepFailed(Exception):
    """A shell command ran but reported a failure in its output."""


class AdbManager:
    """Short-lived ADB sessions to one host (connect, run, close)."""

    def __init__(self, hass: HomeAssistant, host: str, key: AdbKey, port: int = steps.ADB_PORT) -> None:
        """Initialize."""
        self.hass = hass
        self.host = host
        self.port = port
        self._key = key
        self._lock = asyncio.Lock()

    async def _connect(self, auth_timeout: float) -> AdbDeviceAsync:
        device = create_device(self.host, self.port)
        signer = await self.hass.async_add_executor_job(self._key.signer)
        try:
            await device.connect(rsa_keys=[signer], auth_timeout_s=auth_timeout)
        except Exception as err:  # adb_shell raises many exception types
            await _close(device)
            raise AdbError(
                translation_domain=DOMAIN,
                translation_key="adb_connect_failed",
                translation_placeholders={"host": self.host, "error": str(err) or type(err).__name__},
            ) from err
        return device

    async def async_session[T](self, fn: Callable[[AdbDeviceAsync], Awaitable[T]], *, auth_timeout: float = 5) -> T:
        """Run `fn(device)` in an ADB session; errors become AdbError."""
        async with self._lock:
            device = await self._connect(auth_timeout)
            try:
                return await fn(device)
            except AdbError:
                raise
            except Exception as err:
                raise AdbError(
                    translation_domain=DOMAIN,
                    translation_key="adb_command_failed",
                    translation_placeholders={"error": str(err) or type(err).__name__},
                ) from err
            finally:
                await _close(device)

    async def async_is_reachable(self, *, auth_timeout: float = 5) -> bool:
        """Whether an authorized ADB session can be opened."""
        try:
            await self.async_shell("true", auth_timeout=auth_timeout)
        except AdbError:
            return False
        return True

    async def async_shell(self, command: str, *, timeout: float = 30, auth_timeout: float = 5) -> str:
        """Run a shell command and return its output."""

        async def _run(device: AdbDeviceAsync) -> str:
            return await device.shell(command, transport_timeout_s=timeout, read_timeout_s=timeout, timeout_s=timeout)

        return await self.async_session(_run, auth_timeout=auth_timeout)

    async def async_run_steps(
        self,
        commands: list[tuple[str, str]],
        progress: ProgressCallback | None = None,
        *,
        fatal: bool = False,
        auth_timeout: float = 5,
    ) -> dict[str, str]:
        """Run several commands in one session. Returns step -> output."""

        async def _run(device: AdbDeviceAsync) -> dict[str, str]:
            return await self._run_steps(device, commands, progress, fatal=fatal)

        return await self.async_session(_run, auth_timeout=auth_timeout)

    async def _run_steps(
        self,
        device: AdbDeviceAsync,
        commands: list[tuple[str, str]],
        progress: ProgressCallback | None = None,
        *,
        fatal: bool = False,
    ) -> dict[str, str]:
        """Run commands on an open session. Returns step -> output of the steps that worked."""
        results: dict[str, str] = {}
        for step_id, command in commands:
            if progress:
                progress(step_id, {"status": "running", "command": command})
            try:
                output = await device.shell(command, transport_timeout_s=60, read_timeout_s=60, timeout_s=120)
                if steps.looks_failed(output):
                    # most shell tools exit 0 over ADB; the output tells
                    raise _StepFailed(output.strip()[-300:])
            except Exception as err:
                if progress:
                    progress(step_id, {"status": "failed", "error": str(err), "command": command})
                if fatal:
                    raise
                _LOGGER.debug("ADB step %s failed on %s: %s", step_id, self.host, err)
                continue
            results[step_id] = output
            if progress:
                progress(step_id, {"status": "done", "output": output.strip()[-500:]})
        return results

    async def async_platform(self, progress: ProgressCallback | None = None) -> steps.Platform:
        """Android version, serial number and root of the display."""
        if progress:
            progress("root_check", {"status": "running", "command": steps.PLATFORM_CHECK})
        output = await self.async_shell(steps.PLATFORM_CHECK, auth_timeout=60)
        platform = steps.parse_platform(output)
        if progress:
            progress(
                "root_check",
                {"status": "done", "root": platform.root, "sdk": platform.sdk, "output": output.strip()[-500:]},
            )
        return platform

    async def async_setup_adb(self, progress: ProgressCallback | None = None) -> steps.Platform:
        """Make ADB over TCP permanent and trust HA's key. Returns what the platform check found."""
        platform = await self.async_platform(progress)
        await self.async_run_steps(steps.adb_setup_commands(self._key.public, root=platform.root), progress)
        return platform

    async def async_baseline(self) -> dict[str, str]:
        """The stock values the revert restores (read before the first install)."""
        return steps.parse_baseline(await self.async_shell(steps.BASELINE_COMMAND))

    async def async_revert_check(self) -> tuple[steps.Platform, steps.RevertCheck]:
        """Read-only: what a revert would find on the display."""

        async def _run(device: AdbDeviceAsync) -> tuple[steps.Platform, steps.RevertCheck]:
            platform = await device.shell(steps.PLATFORM_CHECK, transport_timeout_s=30, read_timeout_s=30)
            check = await device.shell(steps.REVERT_CHECK, transport_timeout_s=60, read_timeout_s=60)
            return steps.parse_platform(platform), steps.parse_revert_check(check)

        return await self.async_session(_run, auth_timeout=60)

    async def async_disable_adb(self, root: bool, progress: ProgressCallback | None = None) -> None:
        """Turn ADB over the network off; the last command drops the session, which is expected."""
        commands = steps.disable_adb_commands(self._key.public, root=root)

        async def _run(device: AdbDeviceAsync) -> None:
            for step_id, command in commands:
                if progress:
                    progress(step_id, {"status": "running", "command": command})
                try:
                    output = await device.shell(command, transport_timeout_s=15, read_timeout_s=15, timeout_s=20)
                except Exception as err:
                    if step_id == commands[-1][0]:
                        output = ""  # adbd went away as asked
                    else:
                        if progress:
                            progress(step_id, {"status": "failed", "error": str(err) or type(err).__name__})
                        continue
                if progress:
                    progress(step_id, {"status": "done", "output": output.strip()[-300:]})

        await self.async_session(_run)

    async def async_reboot(self) -> None:
        """Reboot the display."""

        async def _run(device: AdbDeviceAsync) -> None:
            await device.reboot(transport_timeout_s=15)

        await self.async_session(_run)

    # ---------------------------------------------------------------- app management

    async def async_install_apk(self, apk: bytes, progress: ProgressCallback | None = None) -> None:
        """Push and install an APK."""

        async def _run(device: AdbDeviceAsync) -> None:
            if progress:
                progress(
                    "push",
                    {"status": "running", "bytes": len(apk), "command": f"push {steps.REMOTE_APK} ({len(apk)} bytes)"},
                )
            await device.push(io.BytesIO(apk), steps.REMOTE_APK, transport_timeout_s=120, read_timeout_s=120)
            if progress:
                progress("push", {"status": "done"})
            for step_id, command in steps.install_commands():
                if progress:
                    progress(step_id, {"status": "running", "command": command})
                output = await device.shell(command, transport_timeout_s=180, read_timeout_s=180, timeout_s=240)
                if step_id == "install" and steps.SIGNATURE_MISMATCH in output:
                    # an old build signed with another key: only an uninstall (or revert) helps
                    raise AdbError(translation_domain=DOMAIN, translation_key="apk_signature_mismatch")
                if step_id == "install" and "Success" not in output:
                    raise AdbError(
                        translation_domain=DOMAIN,
                        translation_key="apk_install_failed",
                        translation_placeholders={"error": output.strip()[-300:]},
                    )
                if progress:
                    progress(step_id, {"status": "done", "output": output.strip()[-300:]})

        await self.async_session(_run, auth_timeout=30)

    async def async_install_app(
        self,
        release: AppRelease | None = None,
        channel: str = UPDATE_CHANNEL_STABLE,
        progress: ProgressCallback | None = None,
        *,
        post_install: bool = True,
        disable_stock: bool = False,
        sdk: int | None = None,
    ) -> AppRelease:
        """Download (latest) app release, install it and run the post-install steps."""
        if release is None:
            release = await async_latest_release(self.hass, channel)
            if release is None:
                raise AdbError(translation_domain=DOMAIN, translation_key="no_release")
        if progress:
            progress("download", {"status": "running", "version": release.version, "command": f"GET {release.apk_url}"})
        apk = await async_download_apk(self.hass, release)
        if progress:
            progress("download", {"status": "done", "bytes": len(apk)})
        await self.async_install_apk(apk, progress)
        if post_install:
            if sdk is None:
                # the permissions differ by android version (bluetooth from 12 on and location before)
                sdk = (await self.async_platform()).sdk
            await self.async_run_steps(steps.post_install_commands(sdk=sdk, disable_stock=disable_stock), progress)
        else:
            await self.async_run_steps(steps.restart_app_commands(), progress)
        return release

    async def async_grant_permissions(self, *, restart: bool = True, auth_timeout: float = 5) -> PermissionGrant:
        """Grant the permissions the app needs (as after an install) and report what changed.

        The app reads some permissions only at start, so it is restarted when a runtime
        permission or the location mode changed (and `restart` is set). WRITE_SECURE_SETTINGS is
        checked when it is used, so it needs no restart.
        """

        async def _run(device: AdbDeviceAsync) -> PermissionGrant:
            platform = steps.parse_platform(
                await device.shell(steps.PLATFORM_CHECK, transport_timeout_s=30, read_timeout_s=30)
            )
            before = steps.parse_permission_check(
                await device.shell(steps.PERMISSION_CHECK, transport_timeout_s=30, read_timeout_s=30)
            )
            commands = steps.permission_commands(sdk=platform.sdk)
            done = await self._run_steps(device, commands)
            after = steps.parse_permission_check(
                await device.shell(steps.PERMISSION_CHECK, transport_timeout_s=30, read_timeout_s=30)
            )
            still_missing = after.missing(platform.sdk)
            granted = [name for name in before.missing(platform.sdk) if name not in still_missing]
            restarted = False
            if restart and any(name != steps.SECURE_SETTINGS_NAME for name in granted):
                await self._run_steps(device, steps.restart_app_commands())
                restarted = True
            return PermissionGrant(
                granted=granted,
                missing=still_missing,
                failed=[step_id for step_id, _ in commands if step_id not in done],
                restarted=restarted,
            )

        return await self.async_session(_run, auth_timeout=auth_timeout)

    async def async_missing_permissions(self, *, auth_timeout: float = 5) -> list[str]:
        """Read-only: what async_grant_permissions would grant (short names and `location_mode`)."""

        async def _run(device: AdbDeviceAsync) -> list[str]:
            platform = steps.parse_platform(
                await device.shell(steps.PLATFORM_CHECK, transport_timeout_s=30, read_timeout_s=30)
            )
            state = steps.parse_permission_check(
                await device.shell(steps.PERMISSION_CHECK, transport_timeout_s=30, read_timeout_s=30)
            )
            return state.missing(platform.sdk)

        return await self.async_session(_run, auth_timeout=auth_timeout)

    async def async_provision(
        self, token: str, client_id: str, client_name: str, settings: dict[str, Any] | None = None
    ) -> str | None:
        """Hand a token (and settings) to the app.

        Returns the certificate fingerprint the app answers with (the broadcast's result data),
        which ADB delivers over a channel HA already trusts.
        """
        output = await self.async_shell(steps.provision_command(token, client_id, client_name, settings))
        if (match := _BROADCAST_DATA.search(output)) is None:
            _LOGGER.debug("Provision broadcast returned no fingerprint: %s", output)
            return None
        return match.group(1).lower()

    async def async_restart_app(self) -> None:
        """Force-stop and start the app."""
        await self.async_run_steps(steps.restart_app_commands(), fatal=True)

    async def async_screenshot(self) -> bytes:
        """PNG screenshot via screencap."""

        async def _run(device: AdbDeviceAsync) -> bytes:
            return await device.exec_out("screencap -p", decode=False, transport_timeout_s=30, read_timeout_s=30)

        return await self.async_session(_run)

    async def async_logcat(self, lines: int = 500) -> str:
        """Recent logcat lines."""
        return await self.async_shell(f"logcat -d -t {int(lines)}", timeout=30)


async def _close(device: AdbDeviceAsync) -> None:
    try:
        await device.close()
    except Exception:
        _LOGGER.debug("Error closing ADB connection", exc_info=True)


async def async_create_adb_manager(hass: HomeAssistant, host: str, port: int = steps.ADB_PORT) -> AdbManager:
    """ADB manager for an arbitrary host (installer)."""
    return AdbManager(hass, host, await async_get_adb_key(hass), port)


class AppWatchdog:
    """Detects 'app down but ADB alive', restarts the app (if enabled) and raises a repair."""

    def __init__(self, device: ShellyElevateIntegrationDevice, adb: AdbManager) -> None:
        """Initialize."""
        self.device = device
        self.adb = adb
        self._timer: CALLBACK_TYPE | None = None
        self._restarts = 0
        self._stopped = False
        self._unsub = device.async_add_availability_listener(self._on_availability)

    @callback
    def _on_availability(self) -> None:
        if self.device.available:
            self._cancel()
            self._restarts = 0
            async_set_app_down(self.device.hass, self.device, False)
        elif self._timer is None:
            self._arm(WATCHDOG_DELAY)

    @callback
    def _arm(self, delay: float) -> None:
        if self._stopped:
            return
        self._cancel()
        self._timer = async_call_later(self.device.hass, delay, self._check)

    def _obsolete(self) -> bool:
        """Stopped (entry unloaded) or the app came back, possibly while we were awaiting ADB."""
        return self._stopped or self.device.available

    @callback
    def _cancel(self) -> None:
        if self._timer:
            self._timer()
            self._timer = None

    async def _check(self, _now: datetime) -> None:
        self._timer = None
        if self._obsolete():
            return
        reachable = await self.adb.async_is_reachable()
        if self._obsolete():
            return
        if not reachable:
            # The whole display is off or away; keep an eye on it without raising anything.
            self._arm(WATCHDOG_MAX_DELAY)
            return
        if self.device.entry.options.get(OPT_WATCHDOG, False) and self._restarts < WATCHDOG_RESTARTS:
            self._restarts += 1
            _LOGGER.warning(
                "%s: app not responding, restarting it via ADB (attempt %s)", self.device.entry.title, self._restarts
            )
            try:
                await self.adb.async_restart_app()
            except AdbError as err:
                _LOGGER.warning("Restarting the app failed: %s", err)
            if self._obsolete():
                return
            self._arm(min(WATCHDOG_DELAY * 2**self._restarts, WATCHDOG_MAX_DELAY))
            return
        # Restarts are off or used up: tell the user, and keep checking in case it comes back.
        async_set_app_down(self.device.hass, self.device, True)
        self._arm(WATCHDOG_MAX_DELAY)

    @callback
    def async_stop(self) -> None:
        """Stop watching and cancel a pending check (a running one finishes without effect)."""
        self._stopped = True
        self._unsub()
        self._cancel()


async def async_get_adb_manager(hass: HomeAssistant, device: ShellyElevateIntegrationDevice) -> AdbManager | None:
    """ADB manager for a configured display, if ADB is enabled for it."""
    enabled = device.entry.options.get(OPT_ADB)
    if enabled is None:
        enabled = bool(device.settings.get("adbWifiEnabled", False))
    if not enabled:
        return None
    adb = AdbManager(hass, device.client.host, await async_get_adb_key(hass))
    watchdog = AppWatchdog(device, adb)
    device.entry.async_on_unload(watchdog.async_stop)
    return adb
