"""ADB command sequences and the parsers of their output."""

from __future__ import annotations

import pytest

from custom_components.shellyelevateintegration.adb import steps

ROOTED = "sdk=30\nserial=0123ABC\nmodel=SAWD-3A1XE10EU2\nuid=0(root) gid=0(root) context=u:r:su:s0\n"
UNROOTED = "sdk=27\nserial=\nmodel=\nuid=2000(shell) gid=2000(shell)\n"
KEY = "QAAAAAbase64key homeassistant@shellyelevateintegration"


def _ids(commands: list[tuple[str, str]]) -> list[str]:
    return [step_id for step_id, _ in commands]


def test_parse_platform() -> None:
    """Android version, serial and root."""
    assert steps.parse_platform(ROOTED) == steps.Platform(sdk=30, serial="0123ABC", model="SAWD-3A1XE10EU2", root=True)
    assert steps.parse_platform(UNROOTED) == steps.Platform(sdk=27, serial=None, model=None, root=False)
    assert steps.parse_platform("garbage").sdk is None


@pytest.mark.parametrize(
    ("output", "failed"),
    [
        ("Success", False),
        ("Error: unknown package", True),
        ("java.lang.SecurityException: Permission Denial", True),
        ("sh: foo: not found", True),
        ("", False),
    ],
)
def test_looks_failed(output: str, failed: bool) -> None:
    """Shell tools exit 0 over ADB; the output tells."""
    assert steps.looks_failed(output) is failed


def test_adb_setup_commands() -> None:
    """Root writes HA's key; without root the shell user does what it can."""
    rooted = steps.adb_setup_commands(KEY, root=True)
    assert _ids(rooted) == ["dev_settings", "adb_enabled", "adb_wifi", "adb_tcp", "adb_key"]
    assert rooted[3][1].startswith("su -c ")
    assert "QAAAAAbase64key" in rooted[4][1]
    plain = steps.adb_setup_commands(KEY, root=False)
    assert _ids(plain) == ["dev_settings", "adb_enabled", "adb_wifi", "adb_tcp"]
    assert not plain[3][1].startswith("su")
    assert _ids(steps.adb_setup_commands(None, root=True))[-1] == "adb_tcp"


def test_parse_baseline() -> None:
    """key=value lines; null and empty values are dropped."""
    output = "screen_brightness_mode=1\nscreen_brightness=null\nstock_disabled=\nhome=cloud.shelly.stargate/.Home\n"
    assert steps.parse_baseline(output) == {"screen_brightness_mode": "1", "home": "cloud.shelly.stargate/.Home"}


def test_install_commands() -> None:
    """Install keeps data, grants and allows downgrades."""
    assert steps.install_commands()[0] == ("install", f"pm install -r -g -d {steps.REMOTE_APK}")


@pytest.mark.parametrize(
    ("sdk", "permissions", "location"),
    [
        (None, ["perm_audio", "perm_location"], True),
        (27, ["perm_audio", "perm_location"], True),
        (30, ["perm_audio", "perm_location"], True),
        (31, ["perm_audio", "perm_bt_scan", "perm_bt_connect"], False),
    ],
)
def test_permission_commands(sdk: int | None, permissions: list[str], location: bool) -> None:
    """Runtime permissions depend on the Android version."""
    commands = steps.permission_commands(sdk=sdk)
    assert [step for step in _ids(commands) if step.startswith("perm_")] == permissions
    assert ("location_on" in _ids(commands)) is location
    assert "secure_settings" in _ids(commands)
    assert steps.needs_location_mode(sdk) is location


def test_location_on_command() -> None:
    """Providers before Android 9, the location mode from Android 9 on."""
    assert "location_providers_allowed" in steps.location_on_command(27)
    assert "location_mode 3" not in steps.location_on_command(27)
    assert steps.location_on_command(29) == "settings put secure location_mode 3"
    both = steps.location_on_command(None)
    assert "location_providers_allowed" in both and "location_mode 3" in both


def test_parse_permission_check() -> None:
    """Granted permissions, location and WRITE_SECURE_SETTINGS."""
    output = (
        "    android.permission.RECORD_AUDIO: granted=true\n"
        "    android.permission.ACCESS_FINE_LOCATION: granted=true\n"
        "location_mode=0\n"
        "location_providers=gps,network\n"
        "secure_requested=2\n"
    )
    state = steps.parse_permission_check(output)
    assert state.granted == {"RECORD_AUDIO", "ACCESS_FINE_LOCATION"}
    assert state.location_on is False
    assert state.providers_on is True
    assert state.secure_settings_requested is True
    # before Android 9 the providers count
    assert state.missing(27) == ["WRITE_SECURE_SETTINGS"]
    assert state.missing(29) == ["location_mode", "WRITE_SECURE_SETTINGS"]
    assert state.missing(31) == ["BLUETOOTH_SCAN", "BLUETOOTH_CONNECT", "WRITE_SECURE_SETTINGS"]

    empty = steps.parse_permission_check("location_mode=null\nlocation_providers=\nsecure_requested=0\n")
    assert empty.location_on is None
    assert empty.providers_on is False
    assert empty.secure_settings_requested is False
    assert empty.missing(27) == ["RECORD_AUDIO", "ACCESS_FINE_LOCATION", "location_mode"]
    assert steps.parse_permission_check("").providers_on is None


def test_post_install_commands() -> None:
    """The stock app is disabled before Android 11 and only kept from drawing on top later."""
    assert _ids(steps.post_install_commands(sdk=27))[-1] == "start"
    old = dict(steps.post_install_commands(sdk=27, disable_stock=True))
    assert old["disable_stock"] == steps.DISABLE_STOCK_COMMAND
    new = dict(steps.post_install_commands(sdk=30, disable_stock=True))
    assert new["disable_stock"] == steps.DISABLE_STOCK_OVERLAY_COMMAND
    assert steps.disable_stock_command(None) == steps.DISABLE_STOCK_OVERLAY_COMMAND


def test_provision_command() -> None:
    """Token and settings are quoted for the shell."""
    command = steps.provision_command("tok'en", "client", "Home Assistant", {"webviewUrl": "http://ha:8123/"})
    assert "--es token 'tok'\"'\"'en'" in command
    assert "--es client_name 'Home Assistant'" in command
    assert '--es settings \'{"webviewUrl":"http://ha:8123/"}\'' in command
    assert "--es settings" not in steps.provision_command("t", "c", "n")
    assert _ids(steps.restart_app_commands()) == ["stop", "start"]


REVERT_OUTPUT = (
    "app=package:/data/app/me.rapierxbox.shellyelevatev2-1/base.apk\n"
    "priv_app=/system/priv-app/ShellyElevateV2\n"
    "init_rc=\n"
    "stock=package:/system/app/Stargate/Stargate.apk\n"
    "stock_disabled=1\n"
    "stock_state=enabled=2\n"
    "stock_home=cloud.shelly.stargate/.MainActivity\n"
    "legacy_v1=package:/data/app/me.rapierxbox.ShellyElevate/base.apk\n"
    "wiki_launcher=package:/data/app/l.l/base.apk\n"
    "wifi_by_app=2\n"
    "leftover_apk=/data/local/tmp/shellyelevate.apk\n"
)


def test_parse_revert_check() -> None:
    """Everything the installation left behind."""
    check = steps.parse_revert_check(REVERT_OUTPUT)
    assert check.app_installed and check.priv_app and not check.init_rc
    assert check.stock_installed and check.stock_disabled and check.stock_disabled_by_root
    assert check.stock_home == "cloud.shelly.stargate/.MainActivity"
    assert check.legacy_v1 and check.wiki_launcher and check.wifi_by_app and check.leftover_apk
    assert check.as_dict()["wifi_by_app"] is True

    clean = steps.parse_revert_check("app=\nstock=package:/x\nstock_home=garbage\nwifi_by_app=x\n")
    assert not clean.app_installed and clean.stock_home is None and not clean.wifi_by_app
    assert steps.parse_revert_check("app=package:/system/priv-app/x.apk\n").priv_app


def test_revert_commands_rooted() -> None:
    """A rooted display gets everything removed, the stock app re-enabled as root."""
    check = steps.parse_revert_check(REVERT_OUTPUT)
    baseline = {"screen_brightness_mode": "1", "screen_brightness": "120", "home": "cloud.shelly.stargate/.Home"}
    commands = dict(steps.revert_commands(check, root=True, baseline=baseline))
    assert next(iter(commands)) == "stop_app"
    assert commands["enable_stock"].startswith("su -c ")
    assert commands["stock_home"] == "cmd package set-home-activity cloud.shelly.stargate/.Home"
    assert commands["brightness_mode"].endswith(" 1")
    assert commands["brightness"].endswith(" 120")
    assert "remove_system_copy" in commands
    assert "uninstall_v1" in commands and "uninstall_launcher" in commands
    assert "/cache/update.zip" in commands["cleanup"]
    assert list(commands)[-1] == "start_stock"


def test_revert_commands_unrooted() -> None:
    """Without root the /system copy is hidden; the home app comes from the check."""
    check = steps.parse_revert_check(REVERT_OUTPUT)
    commands = dict(steps.revert_commands(check, root=False, remove_wiki_launcher=False))
    assert commands["enable_stock"] == "pm enable cloud.shelly.stargate"
    assert commands["stock_home"] == "cmd package set-home-activity cloud.shelly.stargate/.MainActivity"
    assert "hide_system_copy" in commands
    assert "uninstall_launcher" not in commands
    assert "brightness" not in commands
    assert commands["cleanup"] == f"rm -f {steps.REMOTE_APK}"

    nothing = steps.parse_revert_check("app=\n")
    assert _ids(steps.revert_commands(nothing, root=False)) == ["stop_app", "doze_whitelist", "app_ops", "cleanup"]
    init_only = steps.parse_revert_check("init_rc=/system/etc/init/shellyelevate.rc\n")
    assert "hide_system_copy" not in _ids(steps.revert_commands(init_only, root=False))


def test_disable_adb_commands() -> None:
    """HA's key is removed (root) and ADB over the network is turned off last."""
    rooted = steps.disable_adb_commands(KEY, root=True)
    assert _ids(rooted) == ["adb_key", "adb_tcp", "adb_wifi", "dev_settings", "adb_enabled"]
    assert _ids(steps.disable_adb_commands(KEY, root=False))[0] == "adb_tcp"
