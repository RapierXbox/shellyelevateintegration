"""Installer: install and provision a display over ADB, then add it."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import NoURLAvailableError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shellyelevateintegration.adb.baseline import async_get_baseline_store
from custom_components.shellyelevateintegration.adb.manager import AdbError
from custom_components.shellyelevateintegration.adb.steps import Platform
from custom_components.shellyelevateintegration.api import (
    ShellyElevateIntegrationAuthError,
    ShellyElevateIntegrationCertificateError,
    ShellyElevateIntegrationConnectionError,
)
from custom_components.shellyelevateintegration.const import (
    CONF_FEATURES_AUTO_HANDLED,
    CONF_FINGERPRINT,
    CONF_TOKEN,
    DOMAIN,
)
from custom_components.shellyelevateintegration.installer import (
    ProvisionOptions,
    async_provision,
    default_dashboard_url,
)
from custom_components.shellyelevateintegration.settings.profiles import async_get_profile_manager

from .common import FakeDisplay
from .conftest import RELEASES
from .const import DEVICE_ID, FINGERPRINT, HOST, LEGACY_DEVICE_ID, OTHER_FINGERPRINT, TOKEN

INSTALLER = "custom_components.shellyelevateintegration.installer"


@pytest.fixture
def adb() -> Generator[MagicMock]:
    """ADB of a fresh display."""
    manager = MagicMock()
    manager.async_shell = AsyncMock(return_value="")
    manager.async_setup_adb = AsyncMock(return_value=Platform(sdk=27, serial="SER1", model="SAWD", root=True))
    manager.async_baseline = AsyncMock(return_value={"screen_brightness": "180"})
    manager.async_install_app = AsyncMock(return_value=RELEASES[1])
    manager.async_run_steps = AsyncMock(return_value={})
    manager.async_provision = AsyncMock(return_value=FINGERPRINT)
    with patch(f"{INSTALLER}.async_create_adb_manager", AsyncMock(return_value=manager)):
        yield manager


@pytest.fixture
def probe(display: FakeDisplay) -> Generator[AsyncMock]:
    """The app answering once it started."""
    mock = AsyncMock(side_effect=lambda *args, **kwargs: display.hello())
    with patch(f"{INSTALLER}.async_probe", mock):
        yield mock


def _recorder() -> tuple[list[tuple[str, dict[str, Any]]], Any]:
    events: list[tuple[str, dict[str, Any]]] = []
    return events, lambda step, data: events.append((step, data))


def _status(events: list[tuple[str, dict[str, Any]]], step: str) -> str:
    return [data["status"] for name, data in events if name == step][-1]


async def test_provision_new_display(
    hass: HomeAssistant, display: FakeDisplay, adb: MagicMock, probe: AsyncMock
) -> None:
    """Install, hand over a token over ADB, replace it over TLS and add the display."""
    manager = await async_get_profile_manager(hass)
    await manager.async_save_profile("Quiet", {"mediaEnabled": False, "screenSaverDelay": 60}, profile_id="quiet")
    # the app took the profile over ADB
    display.settings |= {"mediaEnabled": False, "bleScannerEnabled": False}
    events, progress = _recorder()
    result = await async_provision(
        hass,
        ProvisionOptions(host=HOST, profile_id="quiet", dashboard_url="http://ha:8123/", disable_stock=True),
        progress,
    )
    await hass.async_block_till_done()
    assert result["display_id"] == DEVICE_ID
    assert result["legacy"] is False
    assert result["device_id"] is not None
    entry = hass.config_entries.async_get_entry(result["entry_id"])
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_TOKEN] == f"{TOKEN}-rotated"  # never the one that crossed ADB
    assert entry.data[CONF_FINGERPRINT] == FINGERPRINT
    # the profile decided media: only the Bluetooth proxy was turned on by the first setup
    assert display.writes == [{"bleScannerEnabled": True}]
    assert CONF_FEATURES_AUTO_HANDLED not in entry.data
    settings = adb.async_provision.await_args.args[3]
    assert settings == {
        "mediaEnabled": False,
        "screenSaverDelay": 60,
        "webviewUrl": "http://ha:8123/",
        "adbWifiEnabled": True,
    }
    adb.async_install_app.assert_awaited_once()
    assert adb.async_install_app.await_args.kwargs == {"progress": progress, "disable_stock": True, "sdk": 27}
    assert (await async_get_baseline_store(hass)).get("SER1") == {"screen_brightness": "180"}
    for step in ("adb_connect", "wait_app", "provision", "config_entry"):
        assert _status(events, step) == "done", step


async def test_provision_existing_display(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay, adb: MagicMock, probe: AsyncMock
) -> None:
    """A display that was added already gets the new token; nothing is installed without asking."""
    await (await async_get_baseline_store(hass)).async_capture("SER1", {"screen_brightness": "1"})
    events, progress = _recorder()
    result = await async_provision(hass, ProvisionOptions(host=HOST, install_app=False), progress)
    await hass.async_block_till_done()
    assert result["entry_id"] == init_integration.entry_id
    assert events[-1] == ("config_entry", {"status": "done", "entry_id": init_integration.entry_id, "updated": True})
    adb.async_install_app.assert_not_awaited()
    adb.async_run_steps.assert_awaited_once()
    adb.async_baseline.assert_not_awaited()


async def test_provision_legacy_app(hass: HomeAssistant, legacy_display: FakeDisplay, adb: MagicMock) -> None:
    """A display that still runs the legacy app gets its settings over HTTP."""
    adb.async_setup_adb.return_value = Platform(sdk=27, serial=None, model=None, root=False)
    with patch(f"{INSTALLER}.async_probe", AsyncMock(return_value=legacy_display.hello())):
        result = await async_provision(hass, ProvisionOptions(host=HOST, version=RELEASES[0].version), lambda *_: None)
    await hass.async_block_till_done()
    assert result["legacy"] is True
    assert result["display_id"] == LEGACY_DEVICE_ID
    assert legacy_display.writes == [{"adbWifiEnabled": True}]
    adb.async_provision.assert_not_awaited()


async def test_adb_not_reachable(hass: HomeAssistant, adb: MagicMock) -> None:
    """Without ADB nothing happens."""
    adb.async_shell.side_effect = AdbError("refused")
    events, progress = _recorder()
    with pytest.raises(AdbError):
        await async_provision(hass, ProvisionOptions(host=HOST), progress)
    assert _status(events, "adb_connect") == "failed"


async def test_stock_values_unreadable(
    hass: HomeAssistant, display: FakeDisplay, adb: MagicMock, probe: AsyncMock
) -> None:
    """Missing stock values do not stop the install."""
    adb.async_baseline.side_effect = AdbError("timeout")
    await async_provision(hass, ProvisionOptions(host=HOST), lambda *_: None)
    await hass.async_block_till_done()
    assert (await async_get_baseline_store(hass)).get("SER1") is None


@pytest.mark.parametrize(
    ("options", "key"), [({"version": "0.0.1"}, "version_not_found"), ({"channel": "stable"}, "no_release")]
)
async def test_no_release(hass: HomeAssistant, adb: MagicMock, options: dict[str, Any], key: str) -> None:
    """The release to install must exist."""
    hass.data["shellyelevateintegration_release_cache"]["releases"] = [RELEASES[0]]
    with pytest.raises(HomeAssistantError) as err:
        await async_provision(hass, ProvisionOptions(host=HOST, **options), lambda *_: None)
    assert err.value.translation_key == key


async def test_app_starts_slowly(hass: HomeAssistant, display: FakeDisplay, adb: MagicMock) -> None:
    """The app is probed until it answers, or until the timeout."""
    probe = AsyncMock(side_effect=[ShellyElevateIntegrationConnectionError("starting"), display.hello()])
    with patch(f"{INSTALLER}.async_probe", probe), patch(f"{INSTALLER}.asyncio.sleep", AsyncMock()):
        await async_provision(hass, ProvisionOptions(host=HOST), lambda *_: None)
    await hass.async_block_till_done()
    assert probe.await_count == 2

    probe = AsyncMock(side_effect=ShellyElevateIntegrationConnectionError("never"))
    with (
        patch(f"{INSTALLER}.async_probe", probe),
        patch(f"{INSTALLER}.asyncio.sleep", AsyncMock()),
        patch(f"{INSTALLER}.APP_START_TIMEOUT", -1),
        pytest.raises(ShellyElevateIntegrationConnectionError),
    ):
        await async_provision(hass, ProvisionOptions(host=HOST), lambda *_: None)


@pytest.mark.parametrize("fingerprint", [None, OTHER_FINGERPRINT])
async def test_certificate_mismatch(
    hass: HomeAssistant, display: FakeDisplay, adb: MagicMock, probe: AsyncMock, fingerprint: str | None
) -> None:
    """The certificate the app reports over ADB must be the one the network shows."""
    adb.async_provision.return_value = fingerprint
    events, progress = _recorder()
    with pytest.raises(HomeAssistantError) as err:
        await async_provision(hass, ProvisionOptions(host=HOST), progress)
    assert err.value.translation_key == "certificate_mismatch"
    assert _status(events, "provision") == "failed"


async def test_token_accepted_late(hass: HomeAssistant, display: FakeDisplay, adb: MagicMock, probe: AsyncMock) -> None:
    """The app takes a moment to accept the token; another certificate or never is an error."""
    display.info_errors = [ShellyElevateIntegrationAuthError("not yet"), ShellyElevateIntegrationConnectionError("x")]
    with patch(f"{INSTALLER}.asyncio.sleep", AsyncMock()):
        await async_provision(hass, ProvisionOptions(host=HOST), lambda *_: None)
    await hass.async_block_till_done()

    display.info_errors = [ShellyElevateIntegrationCertificateError("other")]
    with pytest.raises(HomeAssistantError) as err:
        await async_provision(hass, ProvisionOptions(host=HOST), lambda *_: None)
    assert err.value.translation_key == "certificate_mismatch"

    display.info_errors = [ShellyElevateIntegrationAuthError("never")] * 3
    with (
        patch(f"{INSTALLER}.TOKEN_TIMEOUT", -1),
        pytest.raises(HomeAssistantError) as err,
    ):
        await async_provision(hass, ProvisionOptions(host=HOST), lambda *_: None)
    assert err.value.translation_key == "token_not_accepted"


async def test_config_entry_refused(
    hass: HomeAssistant, display: FakeDisplay, adb: MagicMock, probe: AsyncMock
) -> None:
    """A refused config flow is reported with its translated reason."""
    display.mocks["probe"].side_effect = None
    display.mocks["probe"].return_value = display.hello(fingerprint=OTHER_FINGERPRINT)
    events, progress = _recorder()
    with pytest.raises(HomeAssistantError) as err:
        await async_provision(hass, ProvisionOptions(host=HOST), progress)
    assert err.value.translation_key == "config_entry_failed"
    assert events[-1][1]["reason"] == "certificate_mismatch"
    assert events[-1][1]["error"] != "certificate_mismatch"
    assert not [e for e in hass.config_entries.async_entries(DOMAIN) if e.unique_id == DEVICE_ID]


async def test_default_dashboard_url(hass: HomeAssistant) -> None:
    """The URL of Home Assistant, if it has one."""
    with patch(f"{INSTALLER}.get_url", side_effect=NoURLAvailableError):
        assert default_dashboard_url(hass) is None
    hass.config.internal_url = "http://192.168.1.10:8123"
    assert default_dashboard_url(hass) == "http://192.168.1.10:8123"
