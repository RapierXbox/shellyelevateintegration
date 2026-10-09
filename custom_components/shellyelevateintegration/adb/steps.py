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

ANDROID_9 = 28
ANDROID_11 = 30
ANDROID_12 = 31

SECURE_SETTINGS = "android.permission.WRITE_SECURE_SETTINGS"
SECURE_SETTINGS_NAME = SECURE_SETTINGS.rsplit(".", 1)[-1]

_STOCK_LINE = "'^package:" + STOCK_PACKAGE.replace(".", "\\.") + "$'"
"""grep pattern for exactly the stock package in `pm list packages` (no longer name matches)."""

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
    f" echo stock_disabled=$(pm list packages -d {STOCK_PACKAGE} | grep -c {_STOCK_LINE});"
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


def runtime_permissions(sdk: int | None) -> list[tuple[str, str]]:
    """(step id, permission) of the runtime permissions the app needs on this Android version."""
    perms = [("perm_audio", "android.permission.RECORD_AUDIO")]
    if sdk is None or sdk < ANDROID_12:
        # the manifest only requests location up to android 11 where ble scans need it
        perms.append(("perm_location", "android.permission.ACCESS_FINE_LOCATION"))
    if sdk is not None and sdk >= ANDROID_12:
        # these permissions only exist from Android 12 on
        perms += [
            ("perm_bt_scan", "android.permission.BLUETOOTH_SCAN"),
            ("perm_bt_connect", "android.permission.BLUETOOTH_CONNECT"),
        ]
    return perms


def needs_location_mode(sdk: int | None) -> bool:
    """Whether BLE scans need location turned on (before Android 12 they return nothing while it is off)."""
    return sdk is None or sdk < ANDROID_12


_LOCATION_PROVIDERS_ON = (
    "settings put secure location_providers_allowed +gps; settings put secure location_providers_allowed +network"
)
_LOCATION_MODE_ON = "settings put secure location_mode 3"


def location_on_command(sdk: int | None) -> str:
    """Turn location on.

    Before Android 9 the location mode is only derived from the allowed providers, so writing
    `location_mode` there changes nothing; from Android 9 on `location_mode` is the switch.
    """
    if sdk is None:
        return f"{_LOCATION_PROVIDERS_ON}; {_LOCATION_MODE_ON}"
    if sdk < ANDROID_9:
        return _LOCATION_PROVIDERS_ON
    return _LOCATION_MODE_ON


def permission_commands(*, sdk: int | None = None) -> list[tuple[str, str]]:
    """Grant the runtime permissions and app ops, turn location on and exempt the app from doze.

    Shared by the installer and the permission repair; every command is idempotent and
    failures are not fatal.
    """
    pkg = APP_PACKAGE
    steps = [(step_id, f"pm grant {pkg} {perm}") for step_id, perm in runtime_permissions(sdk)]
    if needs_location_mode(sdk):
        steps.append(("location_on", location_on_command(sdk)))
    steps += [
        ("write_settings", f"appops set {pkg} WRITE_SETTINGS allow"),
        ("overlay", f"appops set {pkg} SYSTEM_ALERT_WINDOW allow"),
        # the app display module reads the app in front from usage stats
        ("usage_stats", f"appops set {pkg} GET_USAGE_STATS allow"),
        ("doze_whitelist", f"dumpsys deviceidle whitelist +{pkg}"),
        # lets the ADB over Wi-Fi switch of the app restart adbd; versions that do not request it are skipped
        (
            "secure_settings",
            f"dumpsys package {pkg} | grep -q {SECURE_SETTINGS} && pm grant {pkg} {SECURE_SETTINGS}; true",
        ),
    ]
    return steps


PERMISSION_CHECK = (
    f"dumpsys package {APP_PACKAGE} | grep -E 'android.permission.[A-Z_]+: granted=true';"
    " echo location_mode=$(settings get secure location_mode);"
    " echo location_providers=$(settings get secure location_providers_allowed);"
    f" echo secure_requested=$(dumpsys package {APP_PACKAGE} | grep -c {SECURE_SETTINGS})"
)
"""Read-only: the granted permissions of the app, the location mode and providers, and whether
the app requests WRITE_SECURE_SETTINGS (versions with the ADB over Wi-Fi switch do)."""

_GRANTED = re.compile(r"android\.permission\.([A-Z_]+): granted=true")


@dataclass(frozen=True, slots=True)
class PermissionState:
    """What PERMISSION_CHECK found."""

    granted: frozenset[str]
    location_on: bool | None
    """None when the location mode could not be read."""
    providers_on: bool | None = None
    """Whether a location provider is allowed (what counts before Android 9), None when not read."""
    secure_settings_requested: bool = False
    """The app requests WRITE_SECURE_SETTINGS, which only ADB can grant."""

    def missing(self, sdk: int | None) -> list[str]:
        """Permissions (short names) and `location_mode` that are still missing."""
        missing = [perm.rsplit(".", 1)[-1] for _, perm in runtime_permissions(sdk)]
        missing = [name for name in missing if name not in self.granted]
        if needs_location_mode(sdk):
            location_on = self.location_on
            if sdk is not None and sdk < ANDROID_9 and self.providers_on is not None:
                location_on = self.providers_on
            if location_on is False:
                missing.append("location_mode")
        if self.secure_settings_requested and SECURE_SETTINGS_NAME not in self.granted:
            missing.append(SECURE_SETTINGS_NAME)
        return missing


def parse_permission_check(output: str) -> PermissionState:
    """Parse the PERMISSION_CHECK output."""
    values = parse_baseline(output)
    mode = values.get("location_mode", "")
    providers: bool | None = None
    for line in output.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == "location_providers":
            # empty or null means no provider is allowed
            providers = value.strip() not in ("", "null")
    requested = values.get("secure_requested", "0")
    return PermissionState(
        granted=frozenset(_GRANTED.findall(output)),
        location_on=int(mode) != 0 if mode.isdigit() else None,
        providers_on=providers,
        secure_settings_requested=requested.isdigit() and int(requested) > 0,
    )


_STOCK_OVERLAY_DENY = f"appops set {STOCK_PACKAGE} SYSTEM_ALERT_WINDOW deny && am force-stop {STOCK_PACKAGE}"

DISABLE_STOCK_OVERLAY_COMMAND = (
    f"{_STOCK_OVERLAY_DENY} && echo 'Stock app kept from drawing on top and stopped'"
    " || echo 'Error: the stock app could not be kept from drawing on top'"
)
"""Keep the stock app from drawing on top and stop it (Android 11 and later).

The stock app stays enabled and stays the home app.
"""

DISABLE_STOCK_COMMAND = (
    f"pm disable-user --user 0 {STOCK_PACKAGE} >/dev/null 2>&1;"
    f" if pm list packages -d {STOCK_PACKAGE} | grep -q {_STOCK_LINE}; then echo 'Stock app disabled';"
    f" else {_STOCK_OVERLAY_DENY}"
    " && echo 'Stock app cannot be disabled here; it may no longer draw on top and was stopped'"
    " || echo 'Error: the stock app could neither be disabled nor kept from drawing on top'; fi"
)
"""Disable the stock app, or keep it from drawing on top where it cannot be disabled (before Android 11).

`pm disable-user` works for the shell user (plain `pm disable` needs root) and `pm enable` undoes
it without root. The output says which of the two applied; `revert_commands` undoes both.
"""


def disable_stock_command(sdk: int | None) -> str:
    """The command that keeps the stock app from covering ShellyElevate on this Android version.

    From Android 11 on (XL, X2i, X1i) the stock app is only kept from drawing on top: disabling it
    could leave these models without a home app. Older models try `pm disable-user` first. An
    unknown version takes the safe way.
    """
    if sdk is not None and sdk < ANDROID_11:
        return DISABLE_STOCK_COMMAND
    return DISABLE_STOCK_OVERLAY_COMMAND


def post_install_commands(*, sdk: int | None = None, disable_stock: bool = False) -> list[tuple[str, str]]:
    """ADB shell commands run after installing the app. Failures are not fatal.

    `disable_stock` keeps the stock app from covering ShellyElevate (see disable_stock_command).
    ShellyElevate is no home app (its lite mode keeps the stock UI): it starts on boot and brings
    itself back whenever the home app is in front, so a disabled stock app leaves the display
    without a home app and an enabled one stays the home app.
    """
    steps = permission_commands(sdk=sdk)
    if disable_stock:
        steps.append(("disable_stock", disable_stock_command(sdk)))
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
    f" echo stock_disabled=$(pm list packages -d {STOCK_PACKAGE} | grep -c {_STOCK_LINE});"
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
