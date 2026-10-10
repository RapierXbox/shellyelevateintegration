"""The dashboard login: one refresh token per display, for the dedicated or a picked user."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.auth.models import User
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.shellyelevateintegration.api import ShellyElevateIntegrationConnectionError
from custom_components.shellyelevateintegration.const import (
    CONF_HA_LOGIN_TOKEN,
    DOMAIN,
    OPT_HA_LOGIN,
    OPT_HA_LOGIN_USER,
)
from custom_components.shellyelevateintegration.ha_login import (
    DEDICATED_USER_NAME,
    RETRY_SECONDS,
    async_get_ha_login_manager,
)

from .common import FakeDisplay
from .conftest import entry_data, setup_entry
from .const import DEVICE_ID, TITLE

ORIGIN = "http://homeassistant.local:8123"


@pytest.fixture
def login_display(display: FakeDisplay, hass_owner_user: User) -> FakeDisplay:
    """A display whose app knows the dashboard login, in an onboarded Home Assistant."""
    display.ha_login_supported = True
    return display


@pytest.fixture
async def ws(hass: HomeAssistant, hass_ws_client: WebSocketGenerator):
    """Send a panel command and return its response."""
    client = await hass_ws_client(hass)

    async def send(command: str, **data: Any) -> dict[str, Any]:
        await client.send_json_auto_id({"type": f"{DOMAIN}/{command}", **data})
        return await client.receive_json()

    return send


def _token(hass: HomeAssistant, entry: MockConfigEntry):
    token_id = entry.data.get(CONF_HA_LOGIN_TOKEN)
    return hass.auth.async_get_refresh_token(token_id) if token_id else None


async def _person(hass: HomeAssistant, name: str) -> User:
    return await hass.auth.async_create_user(name, group_ids=["system-users"])


async def test_logs_in_as_dedicated_user(
    hass: HomeAssistant, login_display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """A new display gets a token of the dedicated non-admin, local-only user for its dashboard origin."""
    await setup_entry(hass, mock_config_entry)
    token = _token(hass, mock_config_entry)
    assert token is not None
    assert token.client_id == f"{ORIGIN}/"
    assert token.client_name == f"{DEDICATED_USER_NAME}: {TITLE}"
    user = token.user
    assert user.name == DEDICATED_USER_NAME
    assert user.local_only
    assert not user.is_admin
    assert not user.system_generated
    assert login_display.ha_login == {
        "origin": ORIGIN,
        "client_id": f"{ORIGIN}/",
        "refresh_token": token.token,
        "user": DEDICATED_USER_NAME,
    }
    assert mock_config_entry.runtime_data.ha_login.status == "ok"
    # the display's other commands never see the login check
    assert login_display.commands == []


async def test_displays_share_the_dedicated_user(
    hass: HomeAssistant,
    login_display: FakeDisplay,
    mock_config_entry: MockConfigEntry,
    second_display: tuple[FakeDisplay, MockConfigEntry],
) -> None:
    """Every display has its own token but the dedicated user is created once."""
    await setup_entry(hass, mock_config_entry)
    other, other_entry = second_display
    other.ha_login_supported = True
    await other_entry.runtime_data.ha_login.async_check()
    first, second = _token(hass, mock_config_entry), _token(hass, other_entry)
    assert first is not None and second is not None
    assert first.id != second.id
    assert first.user.id == second.user.id
    users = [user for user in await hass.auth.async_get_users() if user.name == DEDICATED_USER_NAME]
    assert len(users) == 1


async def test_recreates_deleted_dedicated_user(
    hass: HomeAssistant, login_display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """Deleting the dedicated user makes the next login create it again."""
    await setup_entry(hass, mock_config_entry)
    old = _token(hass, mock_config_entry)
    assert old is not None
    await hass.auth.async_remove_user(old.user)
    login_display.ha_login = None
    await mock_config_entry.runtime_data.ha_login.async_check(force=True)
    new = _token(hass, mock_config_entry)
    assert new is not None
    assert new.user.name == DEDICATED_USER_NAME
    assert new.user.id != old.user.id


async def test_picked_user_of_the_display(hass: HomeAssistant, login_display: FakeDisplay) -> None:
    """The user picked in the options of the display wins over the default."""
    person = await _person(hass, "Wall")
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        title=TITLE,
        unique_id=DEVICE_ID,
        data=entry_data(),
        options={OPT_HA_LOGIN_USER: person.id},
    )
    await setup_entry(hass, entry)
    token = _token(hass, entry)
    assert token is not None
    assert token.user.id == person.id
    assert login_display.ha_login is not None
    assert login_display.ha_login["user"] == "Wall"


async def test_gone_picked_user_falls_back(hass: HomeAssistant, login_display: FakeDisplay) -> None:
    """A picked user that no longer exists falls back to the dedicated user."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        title=TITLE,
        unique_id=DEVICE_ID,
        data=entry_data(),
        options={OPT_HA_LOGIN_USER: "missing"},
    )
    await setup_entry(hass, entry)
    token = _token(hass, entry)
    assert token is not None
    assert token.user.name == DEDICATED_USER_NAME


async def test_default_user_from_the_panel(
    hass: HomeAssistant, login_display: FakeDisplay, mock_config_entry: MockConfigEntry, ws
) -> None:
    """A new default logs the displays in again as that user and revokes the old token."""
    await setup_entry(hass, mock_config_entry)
    old = _token(hass, mock_config_entry)
    assert old is not None
    person = await _person(hass, "Kiosk")

    result = await ws("ha_login/config")
    assert result["success"]
    assert result["result"]["default_user_id"] is None
    assert result["result"]["dedicated_user_id"] == old.user.id
    users = {user["name"]: user for user in result["result"]["users"]}
    assert users[DEDICATED_USER_NAME]["dedicated"]
    assert not users["Kiosk"]["dedicated"]

    result = await ws("ha_login/set_default", user_id=person.id)
    assert result["success"]
    await hass.async_block_till_done()
    new = _token(hass, mock_config_entry)
    assert new is not None
    assert new.user.id == person.id
    assert hass.auth.async_get_refresh_token(old.id) is None
    manager = await async_get_ha_login_manager(hass)
    assert manager.default_user_id == person.id

    result = await ws("ha_login/set_default", user_id="missing")
    assert not result["success"]
    assert manager.default_user_id == person.id


async def test_refused_login_gets_a_new_token_later(
    hass: HomeAssistant, login_display: FakeDisplay, mock_config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """A login the frontend refused is replaced, but not more often than every few minutes."""
    await setup_entry(hass, mock_config_entry)
    first = _token(hass, mock_config_entry)
    assert first is not None
    login = mock_config_entry.runtime_data.ha_login

    login_display.ha_login_refused = True
    mock_config_entry.runtime_data.client.push_state({"ha_login.state": "invalid"})
    await hass.async_block_till_done()
    assert login.status == "invalid"
    assert _token(hass, mock_config_entry) == first

    freezer.tick(timedelta(seconds=RETRY_SECONDS + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    second = _token(hass, mock_config_entry)
    assert second is not None
    assert second.id != first.id
    assert hass.auth.async_get_refresh_token(first.id) is None
    assert login.status == "ok"


async def test_new_dashboard_origin_gets_a_new_token(
    hass: HomeAssistant, login_display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """The app drops the login when the dashboard moves; the integration makes one for the new origin."""
    await setup_entry(hass, mock_config_entry)
    login_display.settings["webviewUrl"] = "https://ha.example.org/lovelace/0"
    await mock_config_entry.runtime_data.ha_login.async_check(force=True)
    token = _token(hass, mock_config_entry)
    assert token is not None
    assert token.client_id == "https://ha.example.org/"
    assert login_display.ha_login is not None
    assert login_display.ha_login["origin"] == "https://ha.example.org"


async def test_dashboard_url_set_later(
    hass: HomeAssistant, login_display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """A display paired without a dashboard url logs in once the url is set."""
    login_display.settings["webviewUrl"] = ""
    await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.runtime_data.ha_login.status == "no_dashboard"
    mock_config_entry.runtime_data.client.push(
        {"type": "settings_changed", "changes": {"webviewUrl": "http://10.0.0.5:8123/"}}
    )
    await hass.async_block_till_done()
    token = _token(hass, mock_config_entry)
    assert token is not None
    assert token.client_id == "http://10.0.0.5:8123/"
    assert mock_config_entry.runtime_data.ha_login.status == "ok"


async def test_logout_and_login_from_the_panel(
    hass: HomeAssistant, login_display: FakeDisplay, mock_config_entry: MockConfigEntry, ws
) -> None:
    """Log out drops the login on both sides and turns it off; log in turns it back on."""
    await setup_entry(hass, mock_config_entry)
    token = _token(hass, mock_config_entry)
    assert token is not None

    result = await ws("ha_login/logout", entry_ids=[mock_config_entry.entry_id])
    assert result["result"]["results"][mock_config_entry.entry_id] == {"ok": True, "status": "off"}
    assert login_display.ha_login is None
    assert hass.auth.async_get_refresh_token(token.id) is None
    assert CONF_HA_LOGIN_TOKEN not in mock_config_entry.data
    assert mock_config_entry.options[OPT_HA_LOGIN] is False

    # off stays off while the display reports no login
    mock_config_entry.runtime_data.client.push_state({"ha_login.state": "none"})
    await hass.async_block_till_done()
    assert login_display.ha_login is None

    result = await ws("ha_login/login", entry_ids=[mock_config_entry.entry_id])
    assert result["result"]["results"][mock_config_entry.entry_id] == {"ok": True, "status": "ok"}
    assert mock_config_entry.options[OPT_HA_LOGIN] is True
    assert login_display.ha_login is not None
    assert _token(hass, mock_config_entry) is not None


async def test_devices_list_shows_the_login(
    hass: HomeAssistant, login_display: FakeDisplay, mock_config_entry: MockConfigEntry, ws
) -> None:
    """The panel sees the login status of each display."""
    await setup_entry(hass, mock_config_entry)
    result = await ws("devices")
    assert result["result"]["devices"][0]["ha_login"] == "ok"


async def test_not_onboarded(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> None:
    """Before onboarding no user is created: the first person becomes the owner."""
    display.ha_login_supported = True
    await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.runtime_data.ha_login.status == "pending"
    assert all(user.system_generated for user in await hass.auth.async_get_users())
    assert display.ha_login is None


async def test_old_app(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry, ws) -> None:
    """An app without the dashboard login is left alone and no user is created."""
    await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.runtime_data.ha_login.status == "unsupported"
    assert CONF_HA_LOGIN_TOKEN not in mock_config_entry.data
    assert not [user for user in await hass.auth.async_get_users() if user.name == DEDICATED_USER_NAME]
    result = await ws("ha_login/login", entry_ids=[mock_config_entry.entry_id])
    assert result["result"]["results"][mock_config_entry.entry_id] == {"ok": False, "status": "unsupported"}


async def test_legacy_app(hass: HomeAssistant, init_legacy: MockConfigEntry) -> None:
    """The legacy app has no dashboard login."""
    assert init_legacy.runtime_data.ha_login is None


async def test_no_dashboard_url(
    hass: HomeAssistant, login_display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """Without a dashboard url there is no origin to make a token for."""
    login_display.settings["webviewUrl"] = ""
    await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.runtime_data.ha_login.status == "no_dashboard"
    assert CONF_HA_LOGIN_TOKEN not in mock_config_entry.data


async def test_hand_over_fails(
    hass: HomeAssistant, login_display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """A token the display did not take is revoked again."""
    login_display.command_errors["ha_login.set"] = ShellyElevateIntegrationConnectionError("gone")
    await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.runtime_data.ha_login.status == "error"
    assert CONF_HA_LOGIN_TOKEN not in mock_config_entry.data
    user = next(user for user in await hass.auth.async_get_users() if user.name == DEDICATED_USER_NAME)
    assert not user.refresh_tokens


async def test_remove_entry_revokes_the_token(
    hass: HomeAssistant, login_display: FakeDisplay, mock_config_entry: MockConfigEntry
) -> None:
    """Removing the display revokes its token but keeps the dedicated user for the others."""
    await setup_entry(hass, mock_config_entry)
    token = _token(hass, mock_config_entry)
    assert token is not None
    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.auth.async_get_refresh_token(token.id) is None
    assert await hass.auth.async_get_user(token.user.id) is not None
