"""Config flow, reauth, reconfigure and options flow."""

from __future__ import annotations

from ipaddress import ip_address
from typing import Any

from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_SYSTEM,
    SOURCE_USER,
    SOURCE_ZEROCONF,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shellyelevateintegration.api import (
    ShellyElevateIntegrationCertificateError,
    ShellyElevateIntegrationCommandError,
    ShellyElevateIntegrationConnectionError,
    ShellyElevateIntegrationPairingError,
)
from custom_components.shellyelevateintegration.config_flow import (
    CONF_CODE,
    CONF_PROFILE,
    NO_PROFILE,
)
from custom_components.shellyelevateintegration.const import (
    CONF_DEVICE_ID,
    CONF_FEATURES_AUTO_ENABLED,
    CONF_FEATURES_AUTO_HANDLED,
    CONF_FINGERPRINT,
    CONF_LEGACY,
    CONF_MAC,
    CONF_PANEL,
    CONF_TOKEN,
    DOMAIN,
    PANEL_UNIQUE_ID,
)
from custom_components.shellyelevateintegration.settings.profiles import async_get_profile_manager

from .common import FakeDisplay
from .conftest import entry_data
from .const import (
    DEVICE_ID,
    FINGERPRINT,
    HOST,
    LEGACY_DEVICE_ID,
    LEGACY_PORT,
    MAC,
    NEW_HOST,
    OTHER_DEVICE_ID,
    OTHER_FINGERPRINT,
    PAIRING_ID,
    PORT,
    TITLE,
    TOKEN,
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

ZEROCONF_INFO = ZeroconfServiceInfo(
    ip_address=ip_address(NEW_HOST),
    ip_addresses=[ip_address(NEW_HOST)],
    hostname=f"{DEVICE_ID}.local.",
    name=f"{TITLE}._shellyelevate._tcp.local.",
    port=PORT,
    type="_shellyelevate._tcp.local.",
    properties={
        "id": DEVICE_ID,
        "name": TITLE,
        "model": "SAWD-2A1XX10EU1",
        "codename": "PEGASUS",
        "fw": "3.26150.1200",
        "api": "1.0",
        "mac": MAC,
        "paired": "0",
    },
)
STOCK_INFO = ZeroconfServiceInfo(
    ip_address=ip_address(HOST),
    ip_addresses=[ip_address(HOST)],
    hostname="ShellyWallDisplay-00082291A2B3.local.",
    name="ShellyWallDisplay-00082291A2B3._shelly._tcp.local.",
    port=80,
    type="_shelly._tcp.local.",
    properties={"gen": "2", "app": "WallDisplay"},
)


def _zeroconf(**properties: Any) -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address=ZEROCONF_INFO.ip_address,
        ip_addresses=ZEROCONF_INFO.ip_addresses,
        hostname=ZEROCONF_INFO.hostname,
        name=ZEROCONF_INFO.name,
        port=ZEROCONF_INFO.port,
        type=ZEROCONF_INFO.type,
        properties={**ZEROCONF_INFO.properties, **properties},
    )


@pytest.fixture
async def panel(hass: HomeAssistant) -> MockConfigEntry:
    """The integration is set up; it adds its panel-only entry by itself."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == {CONF_PANEL: True}
    return entries[0]


async def _start_user(hass: HomeAssistant) -> dict[str, Any]:
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})


def _display_entries(hass: HomeAssistant) -> list[Any]:
    return [entry for entry in hass.config_entries.async_entries(DOMAIN) if not entry.data.get(CONF_PANEL)]


async def _pair(hass: HomeAssistant, result: dict[str, Any], code: str = "123456") -> dict[str, Any]:
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    return await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CODE: code})


# --------------------------------------------------------------------------- user: menu, panel, display


async def test_user_menu_without_panel(hass: HomeAssistant, panel: MockConfigEntry, flow_mocks: dict) -> None:
    """Without the panel entry the user picks a display or only the panel."""
    await hass.config_entries.async_remove(panel.entry_id)
    result = await _start_user(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["display", "panel"]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "panel"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Shelly Elevate panel"
    assert result["data"] == {CONF_PANEL: True}
    assert result["result"].unique_id == PANEL_UNIQUE_ID


async def test_user_menu_display(hass: HomeAssistant, panel: MockConfigEntry, flow_mocks: dict) -> None:
    """The display choice of the menu leads to the address form."""
    await hass.config_entries.async_remove(panel.entry_id)
    result = await _start_user(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "display"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "display"


async def test_system_flow_keeps_single_panel(hass: HomeAssistant, panel: MockConfigEntry) -> None:
    """A second panel entry is never created."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_SYSTEM}, data={})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_manual_display_success(
    hass: HomeAssistant, panel: MockConfigEntry, display: FakeDisplay, flow_mocks: dict
) -> None:
    """Probe, pair with the code from the display, create the entry."""
    result = await _start_user(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "display"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: f" {HOST} ", CONF_PORT: PORT}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["description_placeholders"] == {"name": TITLE, "model": "Wall Display X2", "host": HOST}
    flow_mocks["probe"].assert_awaited_once()
    assert flow_mocks["probe"].await_args.args[1:] == (HOST, PORT)
    pair_start = flow_mocks["pair_start"]
    assert pair_start.await_args.args[1:3] == (HOST, PORT)
    assert pair_start.await_args.args[4] == "Home Assistant (test home)"
    assert pair_start.await_args.kwargs == {"fingerprint": FINGERPRINT}

    result = await _pair(hass, result, " 123456 ")
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TITLE
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_DEVICE_ID: DEVICE_ID,
        CONF_LEGACY: False,
        CONF_TOKEN: TOKEN,
        CONF_FINGERPRINT: FINGERPRINT,
        CONF_MAC: MAC,
        CONF_FEATURES_AUTO_ENABLED: False,
    }
    assert result["result"].unique_id == DEVICE_ID
    assert result["result"].minor_version == 2
    assert flow_mocks["pair_confirm"].await_args.args[1:] == (HOST, PORT, PAIRING_ID, " 123456 ")


async def test_manual_display_cannot_connect(hass: HomeAssistant, panel: MockConfigEntry, flow_mocks: dict) -> None:
    """An unreachable address shows an error and the user can correct it."""
    flow_mocks["probe"].side_effect = ShellyElevateIntegrationConnectionError("timeout")
    result = await _start_user(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    flow_mocks["probe"].side_effect = None
    flow_mocks["probe"].return_value = FakeDisplay().hello()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT})
    result = await _pair(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_manual_display_incompatible_api(
    hass: HomeAssistant, panel: MockConfigEntry, display: FakeDisplay, flow_mocks: dict
) -> None:
    """A display speaking another major version is refused."""
    flow_mocks["probe"].side_effect = None
    flow_mocks["probe"].return_value = display.hello(api_version="2.0")
    result = await _start_user(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "incompatible_api"


async def test_manual_display_already_configured_moves_address(
    hass: HomeAssistant, panel: MockConfigEntry, mock_config_entry: MockConfigEntry, flow_mocks: dict
) -> None:
    """The same display at a new address with the pinned certificate updates the entry."""
    mock_config_entry.add_to_hass(hass)
    result = await _start_user(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: NEW_HOST, CONF_PORT: PORT})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == NEW_HOST


async def test_manual_display_already_configured_other_certificate(
    hass: HomeAssistant,
    panel: MockConfigEntry,
    mock_config_entry: MockConfigEntry,
    display: FakeDisplay,
    flow_mocks: dict,
) -> None:
    """A different certificate never moves a paired entry (its token would go to whoever answers)."""
    mock_config_entry.add_to_hass(hass)
    flow_mocks["probe"].side_effect = None
    flow_mocks["probe"].return_value = display.hello(fingerprint=OTHER_FINGERPRINT)
    result = await _start_user(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: NEW_HOST, CONF_PORT: PORT})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == HOST


async def test_manual_display_unpinned_entry_not_moved(
    hass: HomeAssistant, panel: MockConfigEntry, flow_mocks: dict
) -> None:
    """An entry without a pinned certificate is not moved either."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ID, data=entry_data(**{CONF_FINGERPRINT: None}))
    entry.add_to_hass(hass)
    result = await _start_user(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: NEW_HOST, CONF_PORT: PORT})
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == HOST


async def test_manual_legacy_display(hass: HomeAssistant, panel: MockConfigEntry, legacy_display: FakeDisplay) -> None:
    """The legacy app has no pairing: confirm the warning and create the entry."""
    result = await _start_user(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: LEGACY_PORT}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "legacy_confirm"
    assert result["description_placeholders"]["model"] == "Wall Display X2"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LEGACY] is True
    assert result["data"][CONF_TOKEN] is None
    assert result["data"][CONF_PORT] == LEGACY_PORT
    assert result["result"].unique_id == LEGACY_DEVICE_ID


async def test_manual_legacy_display_moves_legacy_entry(
    hass: HomeAssistant, panel: MockConfigEntry, legacy_display: FakeDisplay, legacy_config_entry: MockConfigEntry
) -> None:
    """A legacy entry follows its display when the user enters the new address."""
    legacy_config_entry.add_to_hass(hass)
    result = await _start_user(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST, CONF_PORT: LEGACY_PORT}
    )
    assert result["reason"] == "already_configured"
    assert legacy_config_entry.data[CONF_HOST] == NEW_HOST


async def test_manual_v1_display_does_not_move_legacy_entry(
    hass: HomeAssistant, panel: MockConfigEntry, legacy_config_entry: MockConfigEntry, flow_mocks: dict
) -> None:
    """An updated app at another address needs the upgrade flow, not a silent move."""
    legacy_config_entry.add_to_hass(hass)
    flow_mocks["probe"].side_effect = None
    flow_mocks["probe"].return_value = FakeDisplay().hello(device_id=LEGACY_DEVICE_ID)
    result = await _start_user(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: NEW_HOST, CONF_PORT: PORT})
    assert result["reason"] == "already_configured"
    assert legacy_config_entry.data[CONF_HOST] == HOST


# --------------------------------------------------------------------------- pairing


async def _at_pair(hass: HomeAssistant) -> dict[str, Any]:
    result = await _start_user(hass)
    return await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: HOST, CONF_PORT: PORT})


@pytest.mark.parametrize(
    ("error", "errors"),
    [
        (ShellyElevateIntegrationPairingError("invalid_code"), {CONF_CODE: "invalid_code"}),
        (ShellyElevateIntegrationPairingError("rate_limited"), {"base": "rate_limited"}),
        (ShellyElevateIntegrationConnectionError("reset"), {"base": "cannot_connect"}),
    ],
)
async def test_pair_errors_recover(
    hass: HomeAssistant, panel: MockConfigEntry, flow_mocks: dict, error: Exception, errors: dict
) -> None:
    """A wrong code, rate limiting or a dropped connection let the user try again."""
    result = await _at_pair(hass)
    flow_mocks["pair_confirm"].side_effect = error
    result = await _pair(hass, result)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors
    assert flow_mocks["pair_start"].await_count == 1  # the code on the display stays valid

    flow_mocks["pair_confirm"].side_effect = None
    result = await _pair(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_pair_expired_starts_new_pairing(hass: HomeAssistant, panel: MockConfigEntry, flow_mocks: dict) -> None:
    """An expired code makes the display show a new one."""
    result = await _at_pair(hass)
    flow_mocks["pair_confirm"].side_effect = ShellyElevateIntegrationPairingError("expired")
    result = await _pair(hass, result)
    assert result["errors"] == {"base": "pairing_expired"}
    assert flow_mocks["pair_start"].await_count == 2

    flow_mocks["pair_confirm"].side_effect = None
    result = await _pair(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_pair_confirm_certificate_mismatch(hass: HomeAssistant, panel: MockConfigEntry, flow_mocks: dict) -> None:
    """Another certificate during pairing aborts (a man in the middle)."""
    result = await _at_pair(hass)
    flow_mocks["pair_confirm"].side_effect = ShellyElevateIntegrationCertificateError("mismatch")
    result = await _pair(hass, result)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "certificate_mismatch"


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (ShellyElevateIntegrationCertificateError("mismatch"), "certificate_mismatch"),
        (ShellyElevateIntegrationPairingError("rate_limited"), "rate_limited"),
        (ShellyElevateIntegrationPairingError("busy"), "cannot_connect"),
        (ShellyElevateIntegrationConnectionError("reset"), "cannot_connect"),
    ],
)
async def test_pair_start_errors(
    hass: HomeAssistant, panel: MockConfigEntry, flow_mocks: dict, error: Exception, reason: str
) -> None:
    """The display refusing to show a code aborts."""
    flow_mocks["pair_start"].side_effect = error
    result = await _at_pair(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


# --------------------------------------------------------------------------- profiles


@pytest.fixture
async def profiles(hass: HomeAssistant) -> None:
    """Two profiles, the first one is the default."""
    manager = await async_get_profile_manager(hass)
    await manager.async_save_profile(
        "Kitchen", {"screenSaverDelay": 120, "mqttDeviceId": "never-copied", "unknownKey": 1}, profile_id="kitchen"
    )
    await manager.async_save_profile("Hall", {"screenSaverDelay": 30}, profile_id="hall")
    await manager.async_save_profile(
        "Quiet", {"mediaEnabled": False, "haVoiceEnabled": False, "screenSaverDelay": 60}, profile_id="quiet"
    )
    assert manager.default_profile_id == "kitchen"


@pytest.mark.usefixtures("profiles")
async def test_profile_applied_to_new_display(
    hass: HomeAssistant, panel: MockConfigEntry, display: FakeDisplay, flow_mocks: dict
) -> None:
    """The chosen profile is written with the new token; per-device and unknown keys are skipped."""
    result = await _pair(hass, await _at_pair(hass))
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "profile"
    schema_default = next(iter(result["data_schema"].schema)).default()
    assert schema_default == "kitchen"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PROFILE: "kitchen"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert display.writes == [{"screenSaverDelay": 120}]
    client = display.clients[-1]
    assert (client.token, client.fingerprint) == (TOKEN, FINGERPRINT)


@pytest.mark.usefixtures("profiles")
async def test_profile_decides_features(
    hass: HomeAssistant, panel: MockConfigEntry, display: FakeDisplay, flow_mocks: dict
) -> None:
    """Features a profile set are not turned on by the first setup."""
    result = await _pair(hass, await _at_pair(hass))
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PROFILE: "quiet"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_FEATURES_AUTO_HANDLED] == ["haVoiceEnabled", "mediaEnabled"]
    assert result["data"][CONF_FEATURES_AUTO_ENABLED] is False


@pytest.mark.usefixtures("profiles")
async def test_no_profile_chosen(
    hass: HomeAssistant, panel: MockConfigEntry, display: FakeDisplay, flow_mocks: dict
) -> None:
    """ "No profile" writes nothing."""
    result = await _pair(hass, await _at_pair(hass))
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PROFILE: NO_PROFILE})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert display.writes == []


@pytest.mark.usefixtures("profiles")
async def test_profile_without_changes(
    hass: HomeAssistant, panel: MockConfigEntry, display: FakeDisplay, flow_mocks: dict
) -> None:
    """A profile whose keys this display does not know writes nothing."""
    display.schema = [item for item in display.schema if item["key"] != "screenSaverDelay"]
    result = await _pair(hass, await _at_pair(hass))
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PROFILE: "hall"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert display.writes == []


@pytest.mark.usefixtures("profiles")
async def test_profile_schema_unavailable(
    hass: HomeAssistant, panel: MockConfigEntry, display: FakeDisplay, flow_mocks: dict
) -> None:
    """Without a schema the profile is applied to the keys the display has."""
    display.schema_error = ShellyElevateIntegrationCommandError("unsupported")
    result = await _pair(hass, await _at_pair(hass))
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PROFILE: "hall"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert display.writes == [{"screenSaverDelay": 30}]


@pytest.mark.usefixtures("profiles")
async def test_profile_failed(
    hass: HomeAssistant, panel: MockConfigEntry, display: FakeDisplay, flow_mocks: dict
) -> None:
    """A failed write shows an error; the display can still be added without a profile."""
    result = await _pair(hass, await _at_pair(hass))
    display.settings_error = ShellyElevateIntegrationConnectionError("reset")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PROFILE: "hall"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "profile_failed"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PROFILE: NO_PROFILE})
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("profiles")
async def test_profile_on_legacy_display(
    hass: HomeAssistant, panel: MockConfigEntry, legacy_display: FakeDisplay
) -> None:
    """The legacy app gets the profile over its HTTP API."""
    result = await _start_user(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: LEGACY_PORT}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "profile"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PROFILE: "kitchen"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert legacy_display.writes == [{"screenSaverDelay": 120}]
    assert legacy_display.clients[-1].device_id == LEGACY_DEVICE_ID


# --------------------------------------------------------------------------- zeroconf


async def test_zeroconf_new_display(
    hass: HomeAssistant, panel: MockConfigEntry, display: FakeDisplay, flow_mocks: dict
) -> None:
    """A discovered display is confirmed, its certificate fetched, then paired."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_INFO)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {"name": TITLE, "model": "Wall Display X2", "host": NEW_HOST}
    flow = hass.config_entries.flow.async_get(result["flow_id"])
    assert flow["context"]["title_placeholders"] == {"name": TITLE}
    flow_mocks["probe"].assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    flow_mocks["probe"].assert_awaited_once()  # TXT records carry no certificate
    result = await _pair(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == NEW_HOST
    assert result["data"][CONF_FINGERPRINT] == FINGERPRINT


async def test_zeroconf_defaults(hass: HomeAssistant, panel: MockConfigEntry, flow_mocks: dict) -> None:
    """A TXT record without name or port still works."""
    info = _zeroconf(name=None)
    info.port = None
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=info)
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"]["name"] == "Shelly Wall Display"


async def test_zeroconf_not_shellyelevate(hass: HomeAssistant, panel: MockConfigEntry) -> None:
    """A service without an id is not a display."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf(id=None)
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_shellyelevateintegration"


async def test_zeroconf_incompatible_api(hass: HomeAssistant, panel: MockConfigEntry) -> None:
    """A display with another protocol major version is not offered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf(api="2.0")
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "incompatible_api"


async def test_zeroconf_ignored(hass: HomeAssistant, panel: MockConfigEntry) -> None:
    """An ignored display stays ignored."""
    MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ID, source=SOURCE_IGNORE, data={}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_INFO)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("hello_changes", "probe_error", "reason", "host"),
    [
        ({}, None, "already_configured", NEW_HOST),
        ({"fingerprint": OTHER_FINGERPRINT}, None, "already_configured", HOST),
        ({"device_id": OTHER_DEVICE_ID}, None, "already_configured", HOST),
        ({}, ShellyElevateIntegrationConnectionError("timeout"), "cannot_connect", HOST),
    ],
)
async def test_zeroconf_known_display_new_address(
    hass: HomeAssistant,
    panel: MockConfigEntry,
    mock_config_entry: MockConfigEntry,
    display: FakeDisplay,
    flow_mocks: dict,
    hello_changes: dict,
    probe_error: Exception | None,
    reason: str,
    host: str,
) -> None:
    """A paired display only moves when the new address presents the pinned certificate."""
    mock_config_entry.add_to_hass(hass)
    flow_mocks["probe"].side_effect = probe_error
    flow_mocks["probe"].return_value = display.hello(**hello_changes)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_INFO)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert mock_config_entry.data[CONF_HOST] == host
    assert flow_mocks["probe"].await_args.args[1:] == (NEW_HOST, PORT)


async def test_zeroconf_known_display_same_address(
    hass: HomeAssistant, panel: MockConfigEntry, mock_config_entry: MockConfigEntry, flow_mocks: dict
) -> None:
    """An announcement at the known address needs no probe."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, data={**mock_config_entry.data, CONF_HOST: NEW_HOST})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_INFO)
    assert result["reason"] == "already_configured"
    flow_mocks["probe"].assert_not_awaited()


async def test_zeroconf_known_legacy_entry(
    hass: HomeAssistant, panel: MockConfigEntry, legacy_config_entry: MockConfigEntry, flow_mocks: dict
) -> None:
    """A legacy entry (nothing to verify) never moves on an announcement."""
    legacy_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_zeroconf(id=LEGACY_DEVICE_ID)
    )
    assert result["reason"] == "already_configured"
    assert legacy_config_entry.data[CONF_HOST] == HOST
    flow_mocks["probe"].assert_not_awaited()


async def test_zeroconf_entry_removed_while_verifying(
    hass: HomeAssistant,
    panel: MockConfigEntry,
    mock_config_entry: MockConfigEntry,
    display: FakeDisplay,
    flow_mocks: dict,
) -> None:
    """The entry is deleted while the new address is probed: nothing is left to update."""
    mock_config_entry.add_to_hass(hass)

    async def probe_and_remove(*args: Any, **kwargs: Any) -> Any:
        await hass.config_entries.async_remove(mock_config_entry.entry_id)
        return display.hello()

    flow_mocks["probe"].side_effect = probe_and_remove
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_INFO)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_confirm_wrong_device(
    hass: HomeAssistant, panel: MockConfigEntry, display: FakeDisplay, flow_mocks: dict
) -> None:
    """Another display answering at the announced address is not paired."""
    flow_mocks["probe"].side_effect = None
    flow_mocks["probe"].return_value = display.hello(device_id=OTHER_DEVICE_ID)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_INFO)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"


async def test_zeroconf_confirm_legacy_answer(hass: HomeAssistant, panel: MockConfigEntry, flow_mocks: dict) -> None:
    """Only the legacy app answering at the announced address is not paired."""
    flow_mocks["probe"].side_effect = None
    flow_mocks["probe"].return_value = FakeDisplay(legacy=True).hello(device_id=DEVICE_ID)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_INFO)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "wrong_device"


async def test_zeroconf_confirm_unreachable(hass: HomeAssistant, panel: MockConfigEntry, flow_mocks: dict) -> None:
    """The display went away between the announcement and the confirmation."""
    flow_mocks["probe"].side_effect = ShellyElevateIntegrationConnectionError("timeout")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=ZEROCONF_INFO)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "cannot_connect"


# --------------------------------------------------------------------------- stock wall display


async def test_wall_display_running_shellyelevate(hass: HomeAssistant, flow_mocks: dict) -> None:
    """A stock announcement of a display that runs ShellyElevate already adds the display."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=STOCK_INFO)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "wall_display_confirm"
    assert result["description_placeholders"] == {"host": HOST}
    flow = hass.config_entries.flow.async_get(result["flow_id"])
    assert flow["context"]["unique_id"] == "wall-display-shellywalldisplay-00082291a2b3"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await _pair(hass, result)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DEVICE_ID


async def test_wall_display_stock_app_adds_panel(hass: HomeAssistant, flow_mocks: dict) -> None:
    """A display with the stock app only gets the panel (its Install tab puts ShellyElevate on it)."""
    flow_mocks["probe"].side_effect = ShellyElevateIntegrationConnectionError("refused")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=STOCK_INFO)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_PANEL: True}


async def test_wall_display_incompatible(hass: HomeAssistant, display: FakeDisplay, flow_mocks: dict) -> None:
    """An app with another protocol major version is refused."""
    flow_mocks["probe"].side_effect = None
    flow_mocks["probe"].return_value = display.hello(api_version="3.1")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=STOCK_INFO)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "incompatible_api"


async def test_wall_display_already_configured(hass: HomeAssistant, flow_mocks: dict) -> None:
    """The display is already added under its own id (an ignored entry does not stop the discovery)."""
    MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ID, source=SOURCE_IGNORE, data={}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=STOCK_INFO)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_wall_display_with_integration_set_up(hass: HomeAssistant, panel: MockConfigEntry) -> None:
    """Once Shelly Elevate is set up the panel installs the app; stock announcements are ignored."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=STOCK_INFO)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_wall_display_ignored(hass: HomeAssistant) -> None:
    """An ignored stock announcement stays ignored."""
    MockConfigEntry(
        domain=DOMAIN, unique_id="wall-display-shellywalldisplay-00082291a2b3", source=SOURCE_IGNORE, data={}
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_ZEROCONF}, data=STOCK_INFO)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# --------------------------------------------------------------------------- installer


def _installer_data(**changes: Any) -> dict[str, Any]:
    return {CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: TOKEN, CONF_FINGERPRINT: FINGERPRINT} | changes


async def test_installer_creates_entry(
    hass: HomeAssistant, panel: MockConfigEntry, display: FakeDisplay, flow_mocks: dict
) -> None:
    """The installer provisioned a token over ADB: the entry is created without pairing."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "installer"}, data=_installer_data())
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == TOKEN
    assert result["data"][CONF_FINGERPRINT] == FINGERPRINT
    flow_mocks["pair_start"].assert_not_awaited()


@pytest.mark.usefixtures("profiles")
async def test_installer_applies_profile(
    hass: HomeAssistant, panel: MockConfigEntry, display: FakeDisplay, flow_mocks: dict
) -> None:
    """The profile the installer was given is written right away."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "installer"}, data=_installer_data(profile="hall")
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert display.writes == [{"screenSaverDelay": 30}]


async def test_installer_features_handled(
    hass: HomeAssistant, panel: MockConfigEntry, display: FakeDisplay, flow_mocks: dict
) -> None:
    """Features the installer already set count as handled (others are ignored)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "installer"},
        data=_installer_data(**{CONF_FEATURES_AUTO_HANDLED: ["mediaEnabled", "webviewUrl"]}),
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_FEATURES_AUTO_HANDLED] == ["mediaEnabled"]


async def test_installer_removes_ignored_entry(hass: HomeAssistant, panel: MockConfigEntry, flow_mocks: dict) -> None:
    """Installing a display on purpose ends ignoring it."""
    MockConfigEntry(domain=DOMAIN, unique_id=DEVICE_ID, source=SOURCE_IGNORE, data={}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "installer"}, data=_installer_data())
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(_display_entries(hass)) == 1


async def test_installer_updates_existing_entry(
    hass: HomeAssistant, panel: MockConfigEntry, legacy_config_entry: MockConfigEntry, flow_mocks: dict
) -> None:
    """A reinstalled display keeps its entry, which takes the verified token and certificate."""
    legacy_config_entry.add_to_hass(hass)
    flow_mocks["probe"].side_effect = None
    flow_mocks["probe"].return_value = FakeDisplay().hello(device_id=LEGACY_DEVICE_ID)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "installer"}, data=_installer_data(**{CONF_HOST: NEW_HOST})
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert legacy_config_entry.data[CONF_HOST] == NEW_HOST
    assert legacy_config_entry.data[CONF_TOKEN] == TOKEN
    assert legacy_config_entry.data[CONF_FINGERPRINT] == FINGERPRINT
    assert legacy_config_entry.data[CONF_LEGACY] is False


async def test_installer_legacy_app(hass: HomeAssistant, panel: MockConfigEntry, legacy_display: FakeDisplay) -> None:
    """The installer can also add a display that still runs the legacy app."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "installer"}, data={CONF_HOST: HOST, CONF_PORT: LEGACY_PORT}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LEGACY] is True


@pytest.mark.parametrize(
    ("data", "probe_error", "reason"),
    [
        (_installer_data(), ShellyElevateIntegrationConnectionError("timeout"), "cannot_connect"),
        (_installer_data(**{CONF_TOKEN: None}), None, "cannot_connect"),
        (_installer_data(**{CONF_FINGERPRINT: OTHER_FINGERPRINT}), None, "certificate_mismatch"),
    ],
)
async def test_installer_aborts(
    hass: HomeAssistant,
    panel: MockConfigEntry,
    flow_mocks: dict,
    data: dict,
    probe_error: Exception | None,
    reason: str,
) -> None:
    """No answer, no token or another certificate than ADB reported abort."""
    flow_mocks["probe"].side_effect = probe_error
    if probe_error is None:
        flow_mocks["probe"].side_effect = None
        flow_mocks["probe"].return_value = FakeDisplay().hello()
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "installer"}, data=data)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


# --------------------------------------------------------------------------- reauth


async def test_reauth_token_rejected(hass: HomeAssistant, mock_config_entry: MockConfigEntry, flow_mocks: dict) -> None:
    """A rejected token is replaced by pairing again."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, data={**mock_config_entry.data, CONF_TOKEN: "old"})
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await _pair(hass, result)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_TOKEN] == TOKEN
    assert mock_config_entry.data[CONF_LEGACY] is False


async def test_reauth_upgrade_from_legacy(
    hass: HomeAssistant, legacy_config_entry: MockConfigEntry, flow_mocks: dict
) -> None:
    """A legacy display that was updated to protocol v1 is paired and switched over."""
    legacy_config_entry.add_to_hass(hass)
    flow_mocks["probe"].side_effect = None
    flow_mocks["probe"].return_value = FakeDisplay().hello(device_id=LEGACY_DEVICE_ID)
    result = await legacy_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "upgrade_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await _pair(hass, result)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "upgrade_successful"
    assert legacy_config_entry.data[CONF_LEGACY] is False
    assert legacy_config_entry.data[CONF_TOKEN] == TOKEN
    assert legacy_config_entry.data[CONF_FINGERPRINT] == FINGERPRINT
    assert legacy_config_entry.data[CONF_PORT] == PORT
    assert legacy_config_entry.data[CONF_MAC] == MAC


@pytest.mark.parametrize(
    ("hello", "probe_error", "reason"),
    [
        (None, ShellyElevateIntegrationConnectionError("timeout"), "cannot_connect"),
        ({"device_id": OTHER_DEVICE_ID}, None, "wrong_device"),
        ({"api_version": "2.0"}, None, "incompatible_api"),
    ],
)
async def test_reauth_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    display: FakeDisplay,
    flow_mocks: dict,
    hello: dict | None,
    probe_error: Exception | None,
    reason: str,
) -> None:
    """Reauth needs the same display, reachable and compatible."""
    mock_config_entry.add_to_hass(hass)
    flow_mocks["probe"].side_effect = probe_error
    if hello is not None:
        flow_mocks["probe"].side_effect = None
        flow_mocks["probe"].return_value = display.hello(**hello)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_reauth_legacy_not_upgraded(
    hass: HomeAssistant, legacy_config_entry: MockConfigEntry, legacy_display: FakeDisplay
) -> None:
    """The legacy app has nothing to authenticate."""
    legacy_config_entry.add_to_hass(hass)
    result = await legacy_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_upgraded"


# --------------------------------------------------------------------------- reconfigure


async def test_reconfigure_moves_display(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, flow_mocks: dict
) -> None:
    """A new address with the pinned certificate is taken."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    flow_mocks["probe"].side_effect = ShellyElevateIntegrationConnectionError("timeout")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: NEW_HOST, CONF_PORT: PORT})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    flow_mocks["probe"].side_effect = None
    flow_mocks["probe"].return_value = FakeDisplay().hello()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: NEW_HOST, CONF_PORT: PORT})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == NEW_HOST


async def test_reconfigure_wrong_device(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, display: FakeDisplay, flow_mocks: dict
) -> None:
    """Another display at the new address is refused."""
    mock_config_entry.add_to_hass(hass)
    flow_mocks["probe"].side_effect = None
    flow_mocks["probe"].return_value = display.hello(device_id=OTHER_DEVICE_ID)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: NEW_HOST, CONF_PORT: PORT})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"


async def test_reconfigure_other_certificate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, display: FakeDisplay, flow_mocks: dict
) -> None:
    """A different certificate needs pairing, not just a new address."""
    mock_config_entry.add_to_hass(hass)
    flow_mocks["probe"].side_effect = None
    flow_mocks["probe"].return_value = display.hello(fingerprint=OTHER_FINGERPRINT)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: NEW_HOST, CONF_PORT: PORT})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "certificate_mismatch"
    assert mock_config_entry.data[CONF_HOST] == HOST


async def test_reconfigure_legacy_entry_to_updated_app(
    hass: HomeAssistant, legacy_config_entry: MockConfigEntry, flow_mocks: dict
) -> None:
    """A legacy entry moves to an updated app; the upgrade flow then pairs it."""
    legacy_config_entry.add_to_hass(hass)
    flow_mocks["probe"].side_effect = None
    flow_mocks["probe"].return_value = FakeDisplay().hello(device_id=LEGACY_DEVICE_ID)
    result = await legacy_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: NEW_HOST, CONF_PORT: PORT})
    assert result["reason"] == "reconfigure_successful"
    assert legacy_config_entry.data[CONF_HOST] == NEW_HOST
    assert legacy_config_entry.data[CONF_LEGACY] is True


async def test_reconfigure_panel_entry(hass: HomeAssistant, panel_entry: MockConfigEntry) -> None:
    """The panel entry has no address."""
    panel_entry.add_to_hass(hass)
    result = await panel_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "panel_entry"
