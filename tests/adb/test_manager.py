"""ADB manager (with a fake adb-shell device) and the app watchdog."""

from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import timedelta
import io
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.shellyelevateintegration.adb import steps
from custom_components.shellyelevateintegration.adb.keys import AdbKey, generate_key
from custom_components.shellyelevateintegration.adb.manager import (
    WATCHDOG_DELAY,
    WATCHDOG_MAX_DELAY,
    AdbError,
    AdbManager,
    AppWatchdog,
    async_create_adb_manager,
    async_get_adb_manager,
)
from custom_components.shellyelevateintegration.const import DOMAIN, OPT_ADB, OPT_WATCHDOG

from ..common import FakeDisplay
from ..conftest import RELEASES, setup_entry

MANAGER = "custom_components.shellyelevateintegration.adb.manager"
PLATFORM = "sdk=29\nserial=SER1\nmodel=SAWD-2A1XX10EU1\nuid=2000(shell)\n"
BEFORE = "android.permission.RECORD_AUDIO: granted=false\nlocation_mode=3\nsecure_requested=1\n"
AFTER = (
    "android.permission.RECORD_AUDIO: granted=true\n"
    "android.permission.ACCESS_FINE_LOCATION: granted=true\n"
    "location_mode=3\nsecure_requested=1\n"
)


@pytest.fixture(scope="module")
def adb_key() -> AdbKey:
    """One RSA key for all tests (generating one is slow)."""
    return generate_key()


class FakeAdbDevice:
    """adb-shell's AdbDeviceAsync: answers shell commands by the first matching fragment."""

    def __init__(self) -> None:
        """Initialize."""
        self.answers: list[tuple[str, Any]] = []
        self.commands: list[str] = []
        self.connect_error: Exception | None = None
        self.close_error: Exception | None = None
        self.pushed: list[tuple[bytes, str]] = []
        self.rebooted = False
        self.closed = 0

    def answer(self, fragment: str, output: Any) -> None:
        """Answer commands containing `fragment` (an exception is raised, a list is consumed in order)."""
        self.answers.insert(0, (fragment, output))

    async def connect(self, rsa_keys: list[Any], auth_timeout_s: float) -> None:
        if self.connect_error is not None:
            raise self.connect_error

    async def shell(self, command: str, **kwargs: Any) -> str:
        self.commands.append(command)
        for fragment, output in self.answers:
            if fragment in command:
                if isinstance(output, list):
                    output = output.pop(0) if len(output) > 1 else output[0]
                if isinstance(output, Exception):
                    raise output
                return output
        return ""

    async def push(self, stream: io.BytesIO, path: str, **kwargs: Any) -> None:
        self.pushed.append((stream.read(), path))

    async def reboot(self, **kwargs: Any) -> None:
        self.rebooted = True

    async def exec_out(self, command: str, **kwargs: Any) -> bytes:
        return b"\x89PNG-adb"

    async def close(self) -> None:
        self.closed += 1
        if self.close_error is not None:
            raise self.close_error


@pytest.fixture
def device() -> Generator[FakeAdbDevice]:
    """The display's adbd."""
    fake = FakeAdbDevice()
    with patch(f"{MANAGER}.create_device", return_value=fake):
        yield fake


@pytest.fixture
def manager(hass: HomeAssistant, adb_key: AdbKey, device: FakeAdbDevice) -> AdbManager:
    """A manager for the display."""
    return AdbManager(hass, "192.168.1.50", adb_key)


def _recorder() -> tuple[list[tuple[str, dict[str, Any]]], Callable[[str, dict[str, Any]], None]]:
    events: list[tuple[str, dict[str, Any]]] = []
    return events, lambda step, data: events.append((step, data))


async def test_shell(manager: AdbManager, device: FakeAdbDevice) -> None:
    """A command runs in its own session."""
    device.answer("getprop", "11\n")
    assert await manager.async_shell("getprop ro.build.version.release") == "11\n"
    assert device.closed == 1
    assert await manager.async_is_reachable()
    assert await manager.async_logcat(5) == ""
    assert device.commands[-1] == "logcat -d -t 5"
    assert await manager.async_screenshot() == b"\x89PNG-adb"
    await manager.async_reboot()
    assert device.rebooted


async def test_connect_and_command_errors(manager: AdbManager, device: FakeAdbDevice) -> None:
    """Connection and command failures become AdbError; closing errors are only logged."""
    device.connect_error = ConnectionRefusedError()
    with pytest.raises(AdbError) as err:
        await manager.async_shell("true")
    assert err.value.translation_key == "adb_connect_failed"
    assert err.value.translation_placeholders["error"] == "ConnectionRefusedError"
    assert not await manager.async_is_reachable()

    device.connect_error = None
    device.close_error = OSError("already closed")
    device.answer("boom", RuntimeError("transport"))
    with pytest.raises(AdbError) as err:
        await manager.async_shell("boom")
    assert err.value.translation_key == "adb_command_failed"

    async def raises_adb_error(adb_device: Any) -> None:
        raise AdbError("inner")

    with pytest.raises(AdbError, match="inner"):
        await manager.async_session(raises_adb_error)


async def test_run_steps(manager: AdbManager, device: FakeAdbDevice) -> None:
    """Failed steps are reported and skipped unless they are fatal."""
    device.answer("bad", "Error: not allowed")
    device.answer("worse", OSError("gone"))
    events, progress = _recorder()
    results = await manager.async_run_steps([("one", "good"), ("two", "bad"), ("three", "worse")], progress)
    assert results == {"one": ""}
    assert [(step, data["status"]) for step, data in events] == [
        ("one", "running"),
        ("one", "done"),
        ("two", "running"),
        ("two", "failed"),
        ("three", "running"),
        ("three", "failed"),
    ]
    assert await manager.async_run_steps([("one", "good")]) == {"one": ""}
    with pytest.raises(AdbError):
        await manager.async_run_steps([("two", "bad")], fatal=True)
    device.answer("am force-stop", "Error: unknown package")
    with pytest.raises(AdbError):
        await manager.async_restart_app()


async def test_platform_and_setup(manager: AdbManager, device: FakeAdbDevice, adb_key: AdbKey) -> None:
    """The platform check and the ADB setup."""
    device.answer("getprop ro.build.version.sdk", "sdk=25\nserial=S\nmodel=M\nuid=0(root)\n")
    events, progress = _recorder()
    platform = await manager.async_setup_adb(progress)
    assert platform.root and platform.sdk == 25
    assert events[1][1]["root"] is True
    assert any("adb_keys" in command for command in device.commands)
    device.answer("screen_brightness_mode", "screen_brightness_mode=1\nscreen_brightness=200\n")
    assert await manager.async_baseline() == {"screen_brightness_mode": "1", "screen_brightness": "200"}
    assert (await manager.async_platform()).serial == "S"


async def test_revert_check_and_disable(manager: AdbManager, device: FakeAdbDevice) -> None:
    """Read what is installed; turning ADB off loses the session at the end."""
    device.answer("getprop ro.build.version.sdk", PLATFORM)
    device.answer("echo app=", "app=package:/data/app/x\nstock=package:/y\n")
    platform, check = await manager.async_revert_check()
    assert platform.sdk == 29
    assert check.app_installed and check.stock_installed

    device.answer("adb_wifi_enabled 0", OSError("closed"))
    device.answer("adb_enabled 0", OSError("adbd restarted"))
    events, progress = _recorder()
    await manager.async_disable_adb(root=False, progress=progress)
    statuses = {step: data["status"] for step, data in events}
    assert statuses == {"adb_tcp": "done", "adb_wifi": "failed", "dev_settings": "done", "adb_enabled": "done"}
    await manager.async_disable_adb(root=False)


async def test_install_apk(manager: AdbManager, device: FakeAdbDevice) -> None:
    """Push, install, clean up; signature mismatches and failures are errors."""
    device.answer("pm install", "Success")
    events, progress = _recorder()
    await manager.async_install_apk(b"apk-bytes", progress)
    assert device.pushed == [(b"apk-bytes", steps.REMOTE_APK)]
    assert ("push", {"status": "done"}) in events
    await manager.async_install_apk(b"apk-bytes")

    device.answer("pm install", f"Failure [{steps.SIGNATURE_MISMATCH}]")
    with pytest.raises(AdbError) as err:
        await manager.async_install_apk(b"apk")
    assert err.value.translation_key == "apk_signature_mismatch"
    device.answer("pm install", "Failure [INSTALL_FAILED_INSUFFICIENT_STORAGE]")
    with pytest.raises(AdbError) as err:
        await manager.async_install_apk(b"apk")
    assert err.value.translation_key == "apk_install_failed"


async def test_install_app(hass: HomeAssistant, manager: AdbManager, device: FakeAdbDevice) -> None:
    """Download the release, install it and run the post-install or restart steps."""
    device.answer("pm install", "Success")
    device.answer("getprop ro.build.version.sdk", "sdk=31\nuid=2000\n")
    events, progress = _recorder()
    with patch(f"{MANAGER}.async_download_apk", AsyncMock(return_value=b"apk")) as download:
        release = await manager.async_install_app(progress=progress)
        assert release == RELEASES[1]
        assert download.await_args.args[1] == RELEASES[1]
        assert any("BLUETOOTH_SCAN" in command for command in device.commands)  # sdk read for the permissions
        assert ("download", {"status": "done", "bytes": 3}) in events

        device.commands.clear()
        await manager.async_install_app(RELEASES[0], post_install=False)
        assert device.commands[-2:] == [f"am force-stop {steps.APP_PACKAGE}", f"am start -n {steps.APP_ACTIVITY}"]

        await manager.async_install_app(RELEASES[0], sdk=27, disable_stock=True)
        assert steps.DISABLE_STOCK_COMMAND in device.commands

    hass.data["shellyelevateintegration_release_cache"]["releases"] = [RELEASES[0]]
    with pytest.raises(AdbError) as err:
        await manager.async_install_app(channel="stable")
    assert err.value.translation_key == "no_release"


async def test_grant_permissions(manager: AdbManager, device: FakeAdbDevice) -> None:
    """Grant, compare before and after, restart when a runtime permission changed."""
    device.answer("getprop ro.build.version.sdk", PLATFORM)
    device.answer("grep -E", [BEFORE, AFTER])
    device.answer("appops set", "Error: not allowed")
    result = await manager.async_grant_permissions()
    assert result.granted == ["RECORD_AUDIO", "ACCESS_FINE_LOCATION"]
    assert result.missing == ["WRITE_SECURE_SETTINGS"]
    assert "write_settings" in result.failed
    assert result.restarted

    device.answer("grep -E", [BEFORE, AFTER])
    assert not (await manager.async_grant_permissions(restart=False)).restarted

    # only WRITE_SECURE_SETTINGS changed: it needs no restart
    secure_before = "android.permission.RECORD_AUDIO: granted=true\nlocation_mode=3\nsecure_requested=1\n"
    secure_after = secure_before + "android.permission.WRITE_SECURE_SETTINGS: granted=true\n"
    device.answer("grep -E", [secure_before, secure_after])
    result = await manager.async_grant_permissions()
    assert result.granted == ["WRITE_SECURE_SETTINGS"]
    assert not result.restarted

    device.answer("grep -E", BEFORE)
    assert await manager.async_missing_permissions() == [
        "RECORD_AUDIO",
        "ACCESS_FINE_LOCATION",
        "WRITE_SECURE_SETTINGS",
    ]


async def test_provision(manager: AdbManager, device: FakeAdbDevice) -> None:
    """The broadcast answers with the certificate fingerprint."""
    device.answer("am broadcast", f'Broadcast completed: result=-1, data="{"AB" * 32}"')
    assert await manager.async_provision("token", "client", "Home Assistant", {"webviewUrl": "x"}) == "ab" * 32
    device.answer("am broadcast", "Broadcast completed: result=0")
    assert await manager.async_provision("token", "client", "Home Assistant") is None


async def test_create_manager(hass: HomeAssistant) -> None:
    """Managers share Home Assistant's key."""
    first = await async_create_adb_manager(hass, "10.0.0.2")
    second = await async_create_adb_manager(hass, "10.0.0.3", 5556)
    assert first._key is second._key
    assert second.port == 5556


# --------------------------------------------------------------------------- per display and watchdog


@pytest.mark.parametrize(
    ("options", "setting", "enabled"),
    [({}, False, False), ({}, True, True), ({OPT_ADB: True}, False, True), ({OPT_ADB: False}, True, False)],
)
async def test_get_adb_manager(
    hass: HomeAssistant,
    display: FakeDisplay,
    mock_config_entry: MockConfigEntry,
    options: dict[str, Any],
    setting: bool,
    enabled: bool,
) -> None:
    """ADB follows the option, or the display's own ADB setting without one."""
    display.settings["adbWifiEnabled"] = setting
    display.info["capabilities"]["screenshot"] = False
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options=options)
    with (
        patch(f"{MANAGER}.AdbManager.async_is_reachable", AsyncMock(return_value=True)),
        patch(f"{MANAGER}.AdbManager.async_missing_permissions", AsyncMock(return_value=[])),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    device = mock_config_entry.runtime_data
    assert (device.adb is not None) is enabled
    # the screenshot and grant button only exist with ADB
    assert (hass.states.get("image.shelly_wall_display_x2_screenshot") is not None) is enabled
    assert await async_get_adb_manager(hass, device) is not None or not enabled


def _app_down(hass: HomeAssistant, entry: MockConfigEntry) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, f"app_unreachable_{entry.entry_id}")


async def _later(hass: HomeAssistant, seconds: float) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


async def test_watchdog_restarts_app(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """The app is restarted a few times, then the user is told."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={OPT_WATCHDOG: True})
    await setup_entry(hass, mock_config_entry)
    device = mock_config_entry.runtime_data
    adb = MagicMock(async_is_reachable=AsyncMock(return_value=True), async_restart_app=AsyncMock())
    watchdog = AppWatchdog(device, adb)

    display.client.set_available(False)
    display.client.set_available(False)
    await _later(hass, WATCHDOG_DELAY + 1)
    assert adb.async_restart_app.await_count == 1
    adb.async_restart_app.side_effect = AdbError("restart failed")
    elapsed = WATCHDOG_DELAY + 1
    for _ in range(4):
        elapsed += WATCHDOG_MAX_DELAY + 1
        await _later(hass, elapsed)
    assert adb.async_restart_app.await_count == 3
    assert _app_down(hass, mock_config_entry) is not None

    display.client.set_available(True)
    await hass.async_block_till_done()
    assert _app_down(hass, mock_config_entry) is None
    watchdog.async_stop()
    watchdog._arm(1)  # stopped: never armed again
    assert watchdog._timer is None


async def test_watchdog_without_restarts(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """Without the watchdog option only the issue is raised; an unreachable display raises nothing."""
    device = init_integration.runtime_data
    adb = MagicMock(async_is_reachable=AsyncMock(return_value=False), async_restart_app=AsyncMock())
    watchdog = AppWatchdog(device, adb)
    display.client.set_available(False)
    await _later(hass, WATCHDOG_DELAY + 1)
    assert _app_down(hass, init_integration) is None
    adb.async_is_reachable.return_value = True
    await _later(hass, WATCHDOG_DELAY + WATCHDOG_MAX_DELAY + 2)
    assert _app_down(hass, init_integration) is not None
    adb.async_restart_app.assert_not_awaited()
    watchdog.async_stop()


async def test_watchdog_app_comes_back_meanwhile(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """A check that finds the app back (or the watchdog stopped) does nothing."""
    device = init_integration.runtime_data

    async def back_while_checking(**kwargs: Any) -> bool:
        display.client.set_available(True)
        return True

    adb = MagicMock(async_is_reachable=AsyncMock(side_effect=back_while_checking), async_restart_app=AsyncMock())
    watchdog = AppWatchdog(device, adb)
    display.client.set_available(False)
    await _later(hass, WATCHDOG_DELAY + 1)
    assert _app_down(hass, init_integration) is None

    hass.config_entries.async_update_entry(init_integration, options={OPT_WATCHDOG: True})
    await hass.async_block_till_done()
    device = init_integration.runtime_data
    adb.async_is_reachable = AsyncMock(return_value=True)

    async def restart_and_back() -> None:
        display.client.set_available(True)

    adb.async_restart_app = AsyncMock(side_effect=restart_and_back)
    watchdog = AppWatchdog(device, adb)
    display.client.set_available(False)
    await _later(hass, WATCHDOG_DELAY * 3)
    adb.async_restart_app.assert_awaited_once()
    watchdog.async_stop()
    await watchdog._check(dt_util.utcnow())
