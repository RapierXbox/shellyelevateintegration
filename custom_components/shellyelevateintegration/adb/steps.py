"""Install, provisioning and revert command sequences (ADB shell).

Pure functions without Home Assistant imports, so the sequences can be tested (and reused)
on their own.

ADB itself is enabled on the display (Android developer settings, or the ShellyElevate
"ADB over Wi-Fi" setting); these steps start once an ADB session on port 5555 is possible.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
import shlex
from typing import Any

APP_PACKAGE = "me.rapierxbox.shellyelevatev2"
APP_ACTIVITY = f"{APP_PACKAGE}/.MainActivity"
PROVISION_ACTION = f"{APP_PACKAGE}.PROVISION"
PROVISION_RECEIVER = f"{APP_PACKAGE}/.ProvisionReceiver"
STOCK_PACKAGE = "cloud.shelly.stargate"
"""The stock Shelly app; it is also the home app on every model."""
ADB_PORT = 5555
REMOTE_APK = "/data/local/tmp/shellyelevate.apk"

# Left behind by older app versions, the upstream install scripts and the wiki (see revert_commands).
PRIV_APP_DIR = "/system/priv-app/ShellyElevateV2"
INIT_RC = "/system/etc/init/shellyelevate.rc"
LEGACY_V1_PACKAGE = "me.rapierxbox.ShellyElevate"
WIKI_LAUNCHER_PACKAGE = "l.l"
"""Ultra Small Launcher, which the wiki's manual setup installs as a home app."""
CACHE_FILES = ("/cache/update.zip", "/cache/update.zip.part", "/cache/.shellyelevate_probe", "/cache/recovery/command")

ANDROID_11 = 30
ANDROID_12 = 31

# Prints "uid=0(root)..." when `su` works for the shell user (rooted displays).
ROOT_CHECK = "su -c id 2>/dev/null || id"

PLATFORM_CHECK = (
    "echo sdk=$(getprop ro.build.version.sdk);"
    " echo serial=$(getprop ro.serialno);"
    " echo model=$(getprop ro.product.model);"
    f" {ROOT_CHECK}"
)
"""First command of every session: Android version, a stable id for this display, and root."""

# Output of shell commands that "succeeded" at the ADB level but failed on the device.
_FAILURE = re.compile(
    r"(?i)(exception|error:|failure|not allowed|permission denial|unknown (package|command)|not found|denied)"
)


@dataclass(frozen=True, slots=True)
class Platform:
    """What the platform check found out."""

    sdk: int | None
    serial: str | None
    model: str | None
    root: bool


def parse_platform(output: str) -> Platform:
    """Parse the PLATFORM_CHECK output."""
    values = dict(line.split("=", 1) for line in output.splitlines() if "=" in line and not line.startswith("uid"))
    sdk = values.get("sdk", "").strip()
    return Platform(
        sdk=int(sdk) if sdk.isdigit() else None,
        serial=values.get("serial", "").strip() or None,
        model=values.get("model", "").strip() or None,
        root=has_root(output),
    )


def looks_failed(output: str) -> bool:
    """Whether a command's output reports a failure (most shell tools still exit 0 over ADB)."""
    return bool(_FAILURE.search(output))


def _q(value: str) -> str:
    return shlex.quote(value)


def has_root(root_check_output: str) -> bool:
    """Whether the ROOT_CHECK output shows a root shell."""
    return "uid=0" in root_check_output


def _as_root(command: str, root: bool) -> str:
    return f"su -c {_q(command)}" if root else command


def adb_setup_commands(adb_public_key: str | None, *, root: bool) -> list[tuple[str, str]]:
    """Make ADB over the network permanent and trust the installer's key.

    Runs first, in the first ADB session: developer settings and ADB on, ADB on TCP 5555
    across reboots and, on rooted displays, the installer's public key in adb_keys.
    Root-only steps fall back to what the shell user can do; failures are not fatal.
    """
    steps = [
        ("dev_settings", "settings put global development_settings_enabled 1"),
        ("adb_enabled", "settings put global adb_enabled 1"),
        # Android 11+ "Wireless debugging"; harmless on older versions
        ("adb_wifi", "settings put global adb_wifi_enabled 1"),
        (
            "adb_tcp",
            _as_root(f"setprop persist.adb.tcp.port {ADB_PORT}; setprop service.adb.tcp.port {ADB_PORT}", root),
        ),
    ]
    if adb_public_key and root:
        # writing adb_keys needs root
        key = adb_public_key.strip()
        steps.append(
            (
                "adb_key",
                _as_root(
                    "mkdir -p /data/misc/adb"
                    f" && (grep -qF {_q(key.split()[0])} /data/misc/adb/adb_keys 2>/dev/null"
                    f" || echo {_q(key)} >> /data/misc/adb/adb_keys)"
                    " && chown system:shell /data/misc/adb/adb_keys"
                    " && chmod 0640 /data/misc/adb/adb_keys"
                    " && (restorecon /data/misc/adb/adb_keys 2>/dev/null; true)",
                    root,
                ),
            )
        )
    return steps


BASELINE_COMMAND = (
    "echo screen_brightness_mode=$(settings get system screen_brightness_mode);"
    " echo screen_brightness=$(settings get system screen_brightness);"
    f" echo stock_disabled=$(pm list packages -d {STOCK_PACKAGE} | grep -c {STOCK_PACKAGE});"
    " echo home=$(cmd package resolve-activity --brief -a android.intent.action.MAIN"
    " -c android.intent.category.HOME 2>/dev/null | tail -n 1)"
)
"""Read before the first install: the stock values the revert restores."""


def parse_baseline(output: str) -> dict[str, str]:
    """`key=value` lines of BASELINE_COMMAND (values `null` / empty are dropped)."""
    values: dict[str, str] = {}
    for line in output.splitlines():
        key, sep, value = line.partition("=")
        if sep and (value := value.strip()) and value != "null":
            values[key.strip()] = value
    return values


def install_commands() -> list[tuple[str, str]]:
    """ADB shell commands to install an APK already pushed to REMOTE_APK.

    `-d` allows going back from a beta to a stable release.
    """
    return [
        ("install", f"pm install -r -g -d {REMOTE_APK}"),
        ("cleanup", f"rm -f {REMOTE_APK}"),
    ]


SIGNATURE_MISMATCH = "INSTALL_FAILED_UPDATE_INCOMPATIBLE"
"""`pm install` output when the installed app was signed with another key (old builds)."""


def post_install_commands(*, sdk: int | None = None, disable_stock: bool = False) -> list[tuple[str, str]]:
    """ADB shell commands run after installing the app. Failures are not fatal.

    `disable_stock` keeps the stock app from covering ShellyElevate. Android 11 models protect
    the stock package (and it is the only home app), so it is only kept from drawing on top and
    stopped there; older ones disable it, which leaves no home app.
    """
    pkg = APP_PACKAGE
    steps = [
        ("perm_audio", f"pm grant {pkg} android.permission.RECORD_AUDIO"),
        ("perm_location", f"pm grant {pkg} android.permission.ACCESS_FINE_LOCATION"),
    ]
    if sdk is not None and sdk >= ANDROID_12:
        # these permissions only exist from Android 12 on
        steps += [
            ("perm_bt_scan", f"pm grant {pkg} android.permission.BLUETOOTH_SCAN"),
            ("perm_bt_connect", f"pm grant {pkg} android.permission.BLUETOOTH_CONNECT"),
        ]
    steps += [
        ("write_settings", f"appops set {pkg} WRITE_SETTINGS allow"),
        ("overlay", f"appops set {pkg} SYSTEM_ALERT_WINDOW allow"),
        ("doze_whitelist", f"dumpsys deviceidle whitelist +{pkg}"),
    ]
    if disable_stock:
        if sdk is not None and sdk >= ANDROID_11:
            command = f"appops set {STOCK_PACKAGE} SYSTEM_ALERT_WINDOW deny; am force-stop {STOCK_PACKAGE}"
        else:
            command = f"pm disable-user --user 0 {STOCK_PACKAGE}"
        steps.append(("disable_stock", command))
    steps.append(("start", f"am start -n {APP_ACTIVITY}"))
    return steps


def provision_command(
    token: str,
    client_id: str,
    client_name: str,
    settings: dict[str, Any] | None = None,
) -> str:
    """Broadcast that hands a pre-shared token (and optional settings) to the app."""
    cmd = (
        f"am broadcast -a {PROVISION_ACTION} -n {PROVISION_RECEIVER}"
        f" --es token {_q(token)} --es client_id {_q(client_id)} --es client_name {_q(client_name)}"
    )
    if settings:
        cmd += f" --es settings {_q(json.dumps(settings, separators=(',', ':')))}"
    return cmd


def restart_app_commands() -> list[tuple[str, str]]:
    """Force-stop and start the app."""
    return [
        ("stop", f"am force-stop {APP_PACKAGE}"),
        ("start", f"am start -n {APP_ACTIVITY}"),
    ]


# ------------------------------------------------------------------------------------------- revert

REVERT_CHECK = (
    f"echo app=$(pm path {APP_PACKAGE} | head -n 1);"
    f" echo priv_app=$(ls -d {PRIV_APP_DIR} 2>/dev/null);"
    f" echo init_rc=$(ls {INIT_RC} 2>/dev/null);"
    f" echo stock=$(pm path {STOCK_PACKAGE} | head -n 1);"
    f" echo stock_disabled=$(pm list packages -d {STOCK_PACKAGE} | grep -c {STOCK_PACKAGE});"
    f" echo stock_state=$(dumpsys package {STOCK_PACKAGE} | grep -oE 'enabled=[0-9]' | head -n 1);"
    " echo stock_home=$(cmd package query-activities --brief -a android.intent.action.MAIN"
    f" -c android.intent.category.HOME 2>/dev/null | grep -m 1 {STOCK_PACKAGE}/);"
    f" echo legacy_v1=$(pm path {LEGACY_V1_PACKAGE} | head -n 1);"
    f" echo wiki_launcher=$(pm path {WIKI_LAUNCHER_PACKAGE} | head -n 1);"
    f" echo wifi_by_app=$(dumpsys wifi 2>/dev/null | grep -c 'creatorName={APP_PACKAGE}');"
    f" echo leftover_apk=$(ls {REMOTE_APK} 2>/dev/null)"
)
"""Read-only: what is on the display, before anything is changed."""


@dataclass(frozen=True, slots=True)
class RevertCheck:
    """What REVERT_CHECK found."""

    app_installed: bool
    priv_app: bool
    init_rc: bool
    stock_installed: bool
    stock_disabled: bool
    stock_disabled_by_root: bool
    stock_home: str | None
    legacy_v1: bool
    wiki_launcher: bool
    wifi_by_app: bool
    leftover_apk: bool

    def as_dict(self) -> dict[str, Any]:
        """For the panel."""
        return asdict(self)


def parse_revert_check(output: str) -> RevertCheck:
    """Parse the REVERT_CHECK output."""
    values = parse_baseline(output)

    def count(key: str) -> bool:
        value = values.get(key, "0")
        return value.isdigit() and int(value) > 0

    home = values.get("stock_home", "").split()
    return RevertCheck(
        app_installed=values.get("app", "").startswith("package:"),
        priv_app=bool(values.get("priv_app")) or values.get("app", "").startswith("package:/system/"),
        init_rc=bool(values.get("init_rc")),
        stock_installed=values.get("stock", "").startswith("package:"),
        stock_disabled=count("stock_disabled"),
        # `pm disable` (state 2, root) cannot be undone by the shell user; disable-user is 3
        stock_disabled_by_root=values.get("stock_state") == "enabled=2",
        stock_home=home[0] if home and "/" in home[0] else None,
        legacy_v1=values.get("legacy_v1", "").startswith("package:"),
        wiki_launcher=values.get("wiki_launcher", "").startswith("package:"),
        wifi_by_app=count("wifi_by_app"),
        leftover_apk=bool(values.get("leftover_apk")),
    )


def revert_commands(
    check: RevertCheck,
    *,
    root: bool,
    baseline: dict[str, str] | None = None,
    remove_wiki_launcher: bool = True,
) -> list[tuple[str, str]]:
    """Undo everything ShellyElevate and its installation changed, ending with the stock app.

    Order matters: stop the app (its watchdog would restart things), give the display its stock
    home app back before any launcher is removed, then uninstall and remove leftovers. ADB is
    left on (see `disable_adb_commands`, which must run last). Failures are not fatal; the
    caller reports them.
    """
    pkg, stock = APP_PACKAGE, STOCK_PACKAGE
    baseline = baseline or {}
    steps: list[tuple[str, str]] = [("stop_app", f"am force-stop {pkg}")]
    if check.stock_installed:
        # state 2 (`pm disable` as root) needs root to undo; state 3 (disable-user) does not
        steps.append(("enable_stock", _as_root(f"pm enable {stock}", root and check.stock_disabled_by_root)))
        steps.append(("stock_overlay", f"appops set {stock} SYSTEM_ALERT_WINDOW default"))
        home = baseline.get("home") if str(baseline.get("home", "")).startswith(f"{stock}/") else check.stock_home
        if home:
            steps.append(("stock_home", f"cmd package set-home-activity {_q(home)}"))
    steps += [
        ("doze_whitelist", f"dumpsys deviceidle whitelist -{pkg}"),
        (
            "app_ops",
            f"appops set {pkg} WRITE_SETTINGS default; appops set {pkg} SYSTEM_ALERT_WINDOW default;"
            f" appops set {pkg} GET_USAGE_STATS default",
        ),
    ]
    if (mode := baseline.get("screen_brightness_mode")) is not None:
        steps.append(("brightness_mode", f"settings put system screen_brightness_mode {_q(mode)}"))
    if (level := baseline.get("screen_brightness")) is not None:
        steps.append(("brightness", f"settings put system screen_brightness {_q(level)}"))
    if check.app_installed:
        # On a /system copy this only removes the update; the copy itself is removed below.
        steps.append(("uninstall", f"pm uninstall {pkg}"))
    if check.priv_app or check.init_rc:
        if root:
            # Android 7/8 mount /system; system-as-root (Android 10+) mounts /
            remount = "mount -o rw,remount /system 2>/dev/null || mount -o rw,remount /"
            readonly = "mount -o ro,remount /system 2>/dev/null || mount -o ro,remount /"
            steps.append(
                (
                    "remove_system_copy",
                    _as_root(
                        f"{remount}; rm -rf {PRIV_APP_DIR} {INIT_RC};"
                        " rm -f /data/dalvik-cache/*/system@priv-app@ShellyElevateV2@*;"
                        f" {readonly}; true",
                        root,
                    ),
                )
            )
        elif check.priv_app:
            # Without root the /system copy stays; hide it for the user and wipe its data.
            steps.append(("hide_system_copy", f"pm uninstall --user 0 {pkg}"))
    if check.legacy_v1:
        steps.append(("uninstall_v1", f"pm uninstall {LEGACY_V1_PACKAGE}"))
    if check.wiki_launcher and remove_wiki_launcher and check.stock_installed:
        # only once the stock app is the home app again
        steps.append(("uninstall_launcher", f"pm uninstall {WIKI_LAUNCHER_PACKAGE}"))
    cleanup = f"rm -f {REMOTE_APK}"
    if root:
        cleanup += "; " + _as_root(f"rm -f {' '.join(CACHE_FILES)} /data/misc/wifi/wpa_supplicant.conf.new", root)
    steps.append(("cleanup", cleanup))
    if check.stock_installed:
        steps.append(("start_stock", "am start -a android.intent.action.MAIN -c android.intent.category.HOME"))
    return steps


def disable_adb_commands(adb_public_key: str | None, *, root: bool) -> list[tuple[str, str]]:
    """Turn ADB over the network off again. Must be the very last step: the session drops."""
    steps: list[tuple[str, str]] = []
    if adb_public_key and root:
        key = adb_public_key.strip().split()[0]
        # rewrite in place (keeps owner, mode and SELinux label)
        steps.append(
            (
                "adb_key",
                _as_root(
                    f"grep -vF {_q(key)} /data/misc/adb/adb_keys > /data/local/tmp/adb_keys.tmp"
                    " && cat /data/local/tmp/adb_keys.tmp > /data/misc/adb/adb_keys;"
                    " rm -f /data/local/tmp/adb_keys.tmp",
                    root,
                ),
            )
        )
    steps += [
        # takes effect when adbd restarts, so it does not cut this session yet
        ("adb_tcp", _as_root("setprop persist.adb.tcp.port ''; setprop service.adb.tcp.port ''", root)),
        ("adb_wifi", "settings put global adb_wifi_enabled 0"),
        ("dev_settings", "settings put global development_settings_enabled 0"),
        ("adb_enabled", "settings put global adb_enabled 0"),
    ]
    return steps
