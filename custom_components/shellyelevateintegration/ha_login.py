"""Keep the dashboard of every display logged into Home Assistant, so nobody types a password on it.

Each display gets its own refresh token. Its client id is the origin of the display's dashboard url
plus a slash, which is what the frontend refreshes with. The app stores the token for that origin
only and hands it to its WebView when the frontend would show the login page. The token belongs to a
non-admin, local-only user the integration creates, or to a user picked in the panel (the default
for all displays) or in the options of one display.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import time
from typing import TYPE_CHECKING, Any, Final

from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.auth.models import RefreshToken, User
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from .api import ShellyElevateIntegrationCommandError, ShellyElevateIntegrationError
from .const import CONF_HA_LOGIN_TOKEN, DOMAIN, OPT_HA_LOGIN, OPT_HA_LOGIN_USER

if TYPE_CHECKING:
    from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY: Final = f"{DOMAIN}.ha_login"
STORAGE_VERSION: Final = 1
DATA_HA_LOGIN: HassKey[HaLoginManager] = HassKey(f"{DOMAIN}_ha_login")
_LOCK: HassKey[asyncio.Lock] = HassKey(f"{DOMAIN}_ha_login_lock")

DEDICATED_USER_NAME: Final = "Shelly Elevate"
RETRY_SECONDS: Final = 300
"""A display that keeps refusing or losing its login gets a new token at most this often."""
STATE_KEY: Final = "ha_login.state"
"""State key of the app: none, ok or invalid (the frontend refused the token)."""
STATE_OK_APP: Final = "ok"
"""What the app reports while it holds a login it can use."""

STATUS_OK: Final = "ok"
STATUS_PENDING: Final = "pending"
STATUS_INVALID: Final = "invalid"
STATUS_OFF: Final = "off"
STATUS_UNSUPPORTED: Final = "unsupported"
STATUS_NO_DASHBOARD: Final = "no_dashboard"
STATUS_ERROR: Final = "error"


class NotOnboardedError(Exception):
    """Home Assistant has no person yet: a user created now would become the owner."""


def _usable(user: User | None) -> bool:
    return user is not None and user.is_active and not user.system_generated


class HaLoginManager:
    """The login users: the dedicated one and the default for all displays (kept in .storage)."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY, private=True)
        self._lock = asyncio.Lock()
        self.dedicated_user_id: str | None = None
        self.default_user_id: str | None = None
        """User picked in the panel for all displays; None means the dedicated user."""

    async def async_load(self) -> None:
        """Load from storage."""
        data = await self._store.async_load() or {}
        self.dedicated_user_id = data.get("dedicated_user_id")
        self.default_user_id = data.get("default_user_id")

    async def _async_save(self) -> None:
        await self._store.async_save(
            {"dedicated_user_id": self.dedicated_user_id, "default_user_id": self.default_user_id}
        )

    async def async_user(self, user_id: str | None = None) -> User:
        """The user a display logs in as: its own pick, the panel default, else the dedicated user.

        A picked user that was deleted or deactivated falls through to the next one.
        """
        for candidate in (user_id, self.default_user_id):
            if candidate is None:
                continue
            user = await self.hass.auth.async_get_user(candidate)
            if _usable(user):
                assert user is not None
                return user
            _LOGGER.warning("The dashboard login user %s is gone or inactive, using the next one", candidate)
        return await self.async_dedicated_user()

    async def async_dedicated_user(self) -> User:
        """The non-admin, local-only user of the displays; created the first time and after a deletion."""
        async with self._lock:
            if self.dedicated_user_id is not None:
                user = await self.hass.auth.async_get_user(self.dedicated_user_id)
                if _usable(user):
                    assert user is not None
                    return user
            if not any(not user.system_generated for user in await self.hass.auth.async_get_users()):
                # the first person Home Assistant gets is made the owner
                raise NotOnboardedError
            user = await self.hass.auth.async_create_user(
                DEDICATED_USER_NAME, group_ids=[GROUP_ID_USER], local_only=True
            )
            _LOGGER.info("Created the Home Assistant user %s for the display dashboards", DEDICATED_USER_NAME)
            self.dedicated_user_id = user.id
            await self._async_save()
            return user

    async def async_set_default_user(self, user_id: str | None) -> None:
        """Set the user all displays without their own pick log in as (None = the dedicated user)."""
        if user_id is not None and not _usable(await self.hass.auth.async_get_user(user_id)):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="ha_login_user_invalid",
                translation_placeholders={"user": user_id},
            )
        self.default_user_id = user_id
        await self._async_save()

    async def async_users(self) -> list[dict[str, Any]]:
        """Users a dashboard can log in as (active people, no system users)."""
        return [
            {
                "id": user.id,
                "name": user.name or user.id,
                "admin": user.is_admin,
                "local_only": user.local_only,
                "dedicated": user.id == self.dedicated_user_id,
            }
            for user in await self.hass.auth.async_get_users()
            if _usable(user)
        ]


async def async_get_ha_login_manager(hass: HomeAssistant) -> HaLoginManager:
    """Return the (lazily loaded) login manager."""
    if (manager := hass.data.get(DATA_HA_LOGIN)) is not None:
        return manager
    lock = hass.data.setdefault(_LOCK, asyncio.Lock())
    async with lock:
        if (manager := hass.data.get(DATA_HA_LOGIN)) is None:
            manager = HaLoginManager(hass)
            await manager.async_load()
            hass.data[DATA_HA_LOGIN] = manager
    return manager


class DisplayLogin:
    """Keeps one display logged in: issues, replaces and revokes its refresh token."""

    def __init__(self, device: ShellyElevateIntegrationDevice, manager: HaLoginManager) -> None:
        """Initialize."""
        self.device = device
        self.manager = manager
        self.hass = device.hass
        self.entry: ShellyElevateIntegrationConfigEntry = device.entry
        self.status = STATUS_PENDING
        self._lock = asyncio.Lock()
        self._last_issue = 0.0
        self._unsubs: list[Callable[[], None]] = []
        self._retry: Callable[[], None] | None = None

    @property
    def enabled(self) -> bool:
        """Whether the dashboard of this display is kept logged in."""
        return bool(self.entry.options.get(OPT_HA_LOGIN, True))

    @callback
    def async_start(self) -> None:
        """Check now and whenever the display comes back or reports a lost login."""
        self._unsubs += [
            self.device.async_add_availability_listener(self._on_availability),
            self.device.async_add_state_listener(self._on_state),
            self.device.async_add_message_listener(self._on_message),
        ]
        self._schedule()

    @callback
    def async_stop(self) -> None:
        """Stop listening."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._cancel_retry()

    @callback
    def _cancel_retry(self) -> None:
        if self._retry is not None:
            self._retry()
            self._retry = None

    @callback
    def _on_availability(self) -> None:
        if self.device.available:
            self._schedule()

    @callback
    def _on_state(self, changes: dict[str, Any]) -> None:
        if STATE_KEY in changes and changes[STATE_KEY] != STATE_OK_APP:
            self._schedule()

    @callback
    def _on_message(self, message: dict[str, Any]) -> None:
        # a new dashboard url needs a token for its origin even when the state key did not change
        if message.get("type") == "settings_changed" and "webviewUrl" in (message.get("changes") or {}):
            self._schedule_now(force=True)

    @callback
    def _schedule(self, *_: Any) -> None:
        self._retry = None
        self._schedule_now()

    @callback
    def _schedule_now(self, *, force: bool = False) -> None:
        self.entry.async_create_background_task(
            self.hass, self.async_check(force=force), f"{DOMAIN} dashboard login {self.entry.title}"
        )

    async def async_check(self, *, force: bool = False) -> str:
        """Bring the login of the display in line with the options; returns the status."""
        async with self._lock:
            try:
                await self._async_check(force)
            except ShellyElevateIntegrationError as err:
                _LOGGER.debug("Dashboard login of %s not checked: %s", self.entry.title, err)
                self.status = STATUS_ERROR
            return self.status

    async def async_login(self) -> str:
        """Turn the login on for this display and log in now."""
        if not self.enabled:
            self.hass.config_entries.async_update_entry(self.entry, options={**self.entry.options, OPT_HA_LOGIN: True})
        return await self.async_check(force=True)

    async def async_logout(self) -> str:
        """Turn the login off for this display: the display drops it and the token is revoked."""
        if self.enabled:
            self.hass.config_entries.async_update_entry(self.entry, options={**self.entry.options, OPT_HA_LOGIN: False})
        return await self.async_check()

    async def _async_check(self, force: bool) -> None:
        device = self.device
        if device.legacy:
            self.status = STATUS_UNSUPPORTED
            return
        if not device.available:
            return
        if not self.enabled:
            if self.entry.data.get(CONF_HA_LOGIN_TOKEN) or device.state.get(STATE_KEY) not in (None, "none"):
                await self._async_revoke()
            self.status = STATUS_OFF
            return
        try:
            status = await device.client.command("ha_login.status")
        except ShellyElevateIntegrationCommandError as err:
            if err.code in ("unknown_action", "unsupported"):
                # an app from before the dashboard login
                self.status = STATUS_UNSUPPORTED
                return
            raise
        origin = status.get("origin")
        client_id = status.get("client_id")
        if not isinstance(origin, str) or not isinstance(client_id, str):
            self.status = STATUS_NO_DASHBOARD
            return
        try:
            user = await self.manager.async_user(self.entry.options.get(OPT_HA_LOGIN_USER))
        except NotOnboardedError:
            _LOGGER.debug("Home Assistant is not onboarded yet, %s logs in later", self.entry.title)
            self.status = STATUS_PENDING
            return
        token = self._token()
        if (
            status.get("state") == STATE_OK_APP
            and token is not None
            and token.user.id == user.id
            and token.client_id == client_id
        ):
            self.status = STATUS_OK
            return
        wait = RETRY_SECONDS - (time.monotonic() - self._last_issue)
        if not force and self._last_issue and wait > 0:
            self.status = STATUS_INVALID if status.get("state") == "invalid" else STATUS_PENDING
            # tried again once the wait is over
            self._cancel_retry()
            self._retry = async_call_later(self.hass, wait, self._schedule)
            return
        await self._async_issue(origin, client_id, user)

    async def _async_issue(self, origin: str, client_id: str, user: User) -> None:
        self._last_issue = time.monotonic()
        try:
            token = await self.hass.auth.async_create_refresh_token(
                user, client_id=client_id, client_name=f"{DEDICATED_USER_NAME}: {self.entry.title}"
            )
        except ValueError as err:
            _LOGGER.warning("Could not create a dashboard login for %s: %s", self.entry.title, err)
            self.status = STATUS_ERROR
            return
        try:
            await self.device.client.command(
                "ha_login.set", origin=origin, client_id=client_id, refresh_token=token.token, user=user.name or ""
            )
        except ShellyElevateIntegrationError as err:
            self.hass.auth.async_remove_refresh_token(token)
            _LOGGER.warning("Could not hand the dashboard login to %s: %s", self.entry.title, err)
            self.status = STATUS_ERROR
            return
        self._remove_token()
        self._save_token_id(token.id)
        _LOGGER.info("Logged the dashboard of %s in as %s", self.entry.title, user.name)
        self.status = STATUS_OK

    async def _async_revoke(self) -> None:
        try:
            await self.device.client.command("ha_login.clear")
        except ShellyElevateIntegrationError as err:
            _LOGGER.debug("Could not clear the dashboard login on %s: %s", self.entry.title, err)
        self._remove_token()
        self._save_token_id(None)
        _LOGGER.info("Logged the dashboard of %s out", self.entry.title)

    def _token(self) -> RefreshToken | None:
        token_id = self.entry.data.get(CONF_HA_LOGIN_TOKEN)
        return self.hass.auth.async_get_refresh_token(token_id) if token_id else None

    def _remove_token(self) -> None:
        if (token := self._token()) is not None:
            self.hass.auth.async_remove_refresh_token(token)

    def _save_token_id(self, token_id: str | None) -> None:
        data = {**self.entry.data, CONF_HA_LOGIN_TOKEN: token_id}
        if token_id is None:
            data.pop(CONF_HA_LOGIN_TOKEN)
        if data != dict(self.entry.data):
            self.hass.config_entries.async_update_entry(self.entry, data=data)


@callback
def async_remove_token(hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry) -> None:
    """Revoke the refresh token of a removed display (the display drops its copy when unpaired)."""
    token_id = entry.data.get(CONF_HA_LOGIN_TOKEN)
    if token_id and (token := hass.auth.async_get_refresh_token(token_id)) is not None:
        hass.auth.async_remove_refresh_token(token)
