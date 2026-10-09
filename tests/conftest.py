"""Fixtures for the Shelly Elevate tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shellyelevateintegration.adb.apk import _CACHE, AppRelease
from custom_components.shellyelevateintegration.adb.manager import PermissionGrant
from custom_components.shellyelevateintegration.const import (
    CONF_DEVICE_ID,
    CONF_FEATURES_AUTO_ENABLED,
    CONF_FINGERPRINT,
    CONF_LEGACY,
    CONF_MAC,
    CONF_PANEL,
    CONF_TOKEN,
    DOMAIN,
    PANEL_UNIQUE_ID,
)

from .common import PACKAGE, FakeDisplay, patch_display
from .const import (
    DEVICE_ID,
    FINGERPRINT,
    HOST,
    LEGACY_DEVICE_ID,
    LEGACY_PORT,
    MAC,
    NEW_HOST,
    OTHER_DEVICE_ID,
    PORT,
    TITLE,
    TOKEN,
)

RELEASES = [
    AppRelease(
        version="3.26170.1000",
        tag="v3.26170.1000",
        prerelease=True,
        url="https://github.com/RapierXbox/ShellyElevate/releases/tag/v3.26170.1000",
        apk_url="https://github.com/RapierXbox/ShellyElevate/releases/download/v3.26170.1000/ShellyElevate.apk",
        apk_name="ShellyElevate.apk",
        sha256=None,
        notes="Beta",
        published="2026-06-19T10:00:00Z",
    ),
    AppRelease(
        version="3.26160.0900",
        tag="v3.26160.0900",
        prerelease=False,
        url="https://github.com/RapierXbox/ShellyElevate/releases/tag/v3.26160.0900",
        apk_url="https://github.com/RapierXbox/ShellyElevate/releases/download/v3.26160.0900/ShellyElevate.apk",
        apk_name="ShellyElevate.apk",
        sha256="00" * 32,
        notes="Fixes",
        published="2026-06-09T09:00:00Z",
    ),
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the custom integration."""


@pytest.fixture(autouse=True)
def bluetooth_mocked(mock_bluetooth: None) -> None:
    """The integration depends on bluetooth: never touch real adapters."""


@pytest.fixture(autouse=True)
async def voice_stack(hass: HomeAssistant) -> AsyncGenerator[None]:
    """What the Assist pipeline needs (conversation needs the homeassistant component, tts ffmpeg)."""
    assert await async_setup_component(hass, "homeassistant", {})
    with patch("homeassistant.components.ffmpeg.FFVersion.get_version", return_value="6.0"):
        yield


@pytest.fixture(autouse=True)
def release_cache(hass: HomeAssistant) -> list[AppRelease]:
    """GitHub releases of the app, as if fetched a moment ago (no network in tests)."""
    hass.data[_CACHE] = {"releases": list(RELEASES), "at": time.monotonic()}
    return RELEASES


@pytest.fixture(autouse=True)
async def unload_entries(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Unload the displays after each test so no timer or task is left behind."""
    yield
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Create every entity enabled (also the ones disabled by default)."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        new_callable=PropertyMock,
        return_value=True,
    ):
        yield


@pytest.fixture
def display() -> Generator[FakeDisplay]:
    """A Wall Display X2 running ShellyElevate (protocol v1)."""
    fake = FakeDisplay()
    with patch_display(fake) as mocks:
        fake.mocks = mocks
        yield fake


@pytest.fixture
def legacy_display() -> Generator[FakeDisplay]:
    """A Wall Display X2 running the legacy app."""
    fake = FakeDisplay(legacy=True)
    with patch_display(fake) as mocks:
        fake.mocks = mocks
        yield fake


@pytest.fixture
def flow_mocks(display: FakeDisplay) -> dict[str, AsyncMock]:
    """The probe and pairing calls of the config flow (answering for `display`)."""
    return display.mocks


def make_adb() -> MagicMock:
    """An ADB manager of a display whose app permissions are all granted."""
    adb = MagicMock()
    adb.host = HOST
    adb.async_missing_permissions = AsyncMock(return_value=[])
    adb.async_grant_permissions = AsyncMock(
        return_value=PermissionGrant(granted=[], missing=[], failed=[], restarted=False)
    )
    adb.async_screenshot = AsyncMock(return_value=b"adb-png")
    adb.async_logcat = AsyncMock(return_value=f"I/ActivityManager: Start proc 1234 for {HOST}\n")
    adb.async_install_app = AsyncMock(return_value=RELEASES[1])
    adb.async_restart_app = AsyncMock()
    adb.async_shell = AsyncMock(return_value="ok")
    adb.async_is_reachable = AsyncMock(return_value=True)
    return adb


@pytest.fixture
def adb() -> Generator[MagicMock]:
    """ADB is enabled for the display."""
    manager = make_adb()
    with patch(f"{PACKAGE}.adb.manager.async_get_adb_manager", AsyncMock(return_value=manager)):
        yield manager


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Skip setting up the entries a flow creates."""
    with patch(f"{PACKAGE}.async_setup_entry", return_value=True) as mock:
        yield mock


def entry_data(**changes: Any) -> dict[str, Any]:
    """Data of a paired display."""
    return {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_DEVICE_ID: DEVICE_ID,
        CONF_LEGACY: False,
        CONF_TOKEN: TOKEN,
        CONF_FINGERPRINT: FINGERPRINT,
        CONF_MAC: MAC,
        CONF_FEATURES_AUTO_ENABLED: True,
    } | changes


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A paired display."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        title=TITLE,
        unique_id=DEVICE_ID,
        data=entry_data(),
    )


@pytest.fixture
def legacy_config_entry() -> MockConfigEntry:
    """A display running the legacy app."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        title="Shelly Wall Display",
        unique_id=LEGACY_DEVICE_ID,
        data={
            CONF_HOST: HOST,
            CONF_PORT: LEGACY_PORT,
            CONF_DEVICE_ID: LEGACY_DEVICE_ID,
            CONF_LEGACY: True,
            CONF_TOKEN: None,
            CONF_FINGERPRINT: None,
            CONF_MAC: None,
            CONF_FEATURES_AUTO_ENABLED: True,
        },
    )


@pytest.fixture
def panel_entry() -> MockConfigEntry:
    """The panel-only entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        title="Shelly Elevate panel",
        unique_id=PANEL_UNIQUE_ID,
        data={CONF_PANEL: True},
    )


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    """Add and set up an entry."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """A set up display."""
    await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    return mock_config_entry


@pytest.fixture
async def init_legacy(
    hass: HomeAssistant, legacy_display: FakeDisplay, legacy_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """A set up legacy display."""
    await setup_entry(hass, legacy_config_entry)
    assert legacy_config_entry.state is ConfigEntryState.LOADED
    return legacy_config_entry


@pytest.fixture
async def second_display(hass: HomeAssistant, display: FakeDisplay) -> tuple[FakeDisplay, MockConfigEntry]:
    """A second display (an XL) at another address, set up."""
    other = FakeDisplay()
    other.info |= {"id": OTHER_DEVICE_ID, "name": "Shelly Wall Display XL", "mac": "11:22:33:44:55:01"}
    other.info["codename"] = "BLAKE"
    other.settings["mqttDeviceId"] = OTHER_DEVICE_ID
    other.settings["screenSaverDelay"] = 300
    display.others[NEW_HOST] = other
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        title="Shelly Wall Display XL",
        unique_id=OTHER_DEVICE_ID,
        data=entry_data(**{CONF_HOST: NEW_HOST, CONF_DEVICE_ID: OTHER_DEVICE_ID, CONF_MAC: "11:22:33:44:55:01"}),
    )
    await setup_entry(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    return other, entry
