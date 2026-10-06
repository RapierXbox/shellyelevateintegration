"""Installer backend: install and provision a display over ADB.

ADB is enabled on the display itself (Android developer settings or the ShellyElevate
"ADB over Wi-Fi" setting). Home Assistant then installs the app, grants permissions, hands
over a token and settings, and adds the display.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import secrets
import time
from typing import Any

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, instance_id
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.translation import async_get_translations

from .adb import steps
from .adb.apk import async_get_releases, async_latest_release
from .adb.baseline import async_get_baseline_store
from .adb.manager import AdbError, ProgressCallback, async_create_adb_manager
from .api import (
    DEFAULT_PORT,
    Hello,
    LegacyClient,
    ShellyElevateIntegrationAuthError,
    ShellyElevateIntegrationCertificateError,
    ShellyElevateIntegrationClient,
    ShellyElevateIntegrationConnectionError,
    ShellyElevateIntegrationError,
    async_probe,
)
from .const import CONF_FINGERPRINT, CONF_TOKEN, DOMAIN, UPDATE_CHANNEL_STABLE
from .settings.profiles import async_get_profile_manager

_LOGGER = logging.getLogger(__name__)

APP_START_TIMEOUT = 90
TOKEN_TIMEOUT = 20


@dataclass
class ProvisionOptions:
    """What the provisioning should do."""

    host: str
    install_app: bool = True
    channel: str = UPDATE_CHANNEL_STABLE
    version: str | None = None
    """Install exactly this release instead of the latest one of the channel."""
    disable_stock: bool = False
    """Keep the stock app from covering ShellyElevate (see steps.post_install_commands)."""
    profile_id: str | None = None
    dashboard_url: str | None = None
    adb_port: int = steps.ADB_PORT
    app_port: int = DEFAULT_PORT


async def _wait_for_app(hass: HomeAssistant, host: str, port: int) -> Hello:
    """Probe until the freshly started app answers."""
    session = async_get_clientsession(hass)
    deadline = time.monotonic() + APP_START_TIMEOUT
    while True:
        try:
            return await async_probe(session, host, port)
        except ShellyElevateIntegrationConnectionError:
            if time.monotonic() > deadline:
                raise
            await asyncio.sleep(3)


async def async_provision(hass: HomeAssistant, options: ProvisionOptions, progress: ProgressCallback) -> dict[str, Any]:
    """Install the app over ADB, hand it a token and settings, and add it to HA."""
    adb = await async_create_adb_manager(hass, options.host, options.adb_port)

    progress("adb_connect", {"status": "running", "command": f"connect {options.host}:{options.adb_port}"})
    try:
        await adb.async_shell("true", auth_timeout=60)
    except AdbError as err:
        progress("adb_connect", {"status": "failed", "error": str(err)})
        raise
    progress("adb_connect", {"status": "done"})

    # ADB permanently on TCP 5555 + HA's key trusted, so updates and rescue work later
    platform = await adb.async_setup_adb(progress)
    if platform.serial:
        # stock values for a later revert, unless an earlier install already recorded them
        store = await async_get_baseline_store(hass)
        if store.get(platform.serial) is None:
            try:
                await store.async_capture(platform.serial, await adb.async_baseline())
            except AdbError as err:
                _LOGGER.debug("Could not read the stock values of %s: %s", options.host, err)

    if options.install_app:
        if options.version:
            release = next((r for r in await async_get_releases(hass) if r.version == options.version), None)
            if release is None:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="version_not_found",
                    translation_placeholders={"version": options.version},
                )
        else:
            release = await async_latest_release(hass, options.channel)
            if release is None:
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key="no_release")
        await adb.async_install_app(release, progress=progress, disable_stock=options.disable_stock, sdk=platform.sdk)
    else:
        await adb.async_run_steps(
            steps.post_install_commands(sdk=platform.sdk, disable_stock=options.disable_stock), progress
        )

    settings: dict[str, Any] = {}
    if options.profile_id:
        manager = await async_get_profile_manager(hass)
        settings.update(manager.settings_for_device(options.profile_id, None))
    if options.dashboard_url:
        settings["webviewUrl"] = options.dashboard_url
    # ADB stays usable for updates and rescue
    settings["adbWifiEnabled"] = True

    progress("wait_app", {"status": "running"})
    hello = await _wait_for_app(hass, options.host, options.app_port)
    progress("wait_app", {"status": "done", "legacy": hello.legacy, "version": hello.fw_version})

    data: dict[str, Any] = {CONF_HOST: options.host, CONF_PORT: hello.port}
    progress("provision", {"status": "running"})
    try:
        if hello.legacy:
            await LegacyClient(async_get_clientsession(hass), options.host, hello.port).set_settings(settings)
        else:
            token = secrets.token_urlsafe(32)
            fingerprint = await adb.async_provision(
                token, await instance_id.async_get(hass), "Home Assistant", settings
            )
            # The certificate the app reports over ADB must be the one the network shows us.
            if fingerprint is None or fingerprint != hello.fingerprint:
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key="certificate_mismatch")
            # `am broadcast` reports success whether or not the app took the token
            client = await _wait_for_token(hass, options.host, hello.port, token, fingerprint)
            # ADB over TCP is not encrypted: a token that crossed it is replaced at once over TLS.
            token = await client.rotate_token()
            data |= {CONF_TOKEN: token, CONF_FINGERPRINT: fingerprint}
    except (ShellyElevateIntegrationError, HomeAssistantError) as err:
        progress("provision", {"status": "failed", "error": str(err)})
        raise
    progress("provision", {"status": "done"})

    progress("config_entry", {"status": "running"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "installer"}, data=data)
    entry_id: str | None = None
    updated = False
    if result["type"] is FlowResultType.CREATE_ENTRY:
        entry_id = result["result"].entry_id
    elif (
        result["type"] is FlowResultType.ABORT
        and result["reason"] == "already_configured"
        and (entry := hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, hello.device_id))
    ):
        # The display was already added; the flow updated its address and token.
        entry_id, updated = entry.entry_id, True
    if entry_id is None:
        code = str(result.get("reason") or result["type"])
        # The flow's abort reason in the user's language, not the raw key
        translations = await async_get_translations(hass, hass.config.language, "config", [DOMAIN])
        reason = translations.get(f"component.{DOMAIN}.config.abort.{code}", code)
        progress("config_entry", {"status": "failed", "error": reason, "reason": code})
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="config_entry_failed",
            translation_placeholders={"reason": reason},
        )
    progress("config_entry", {"status": "done", "entry_id": entry_id, "updated": updated})
    # The HA device exists once the entry has been set up; the panel falls back to its display list.
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, hello.device_id)})
    return {
        "entry_id": entry_id,
        "device_id": device.id if device else None,
        "display_id": hello.device_id,
        "legacy": hello.legacy,
        "name": hello.name,
    }


async def _wait_for_token(
    hass: HomeAssistant, host: str, port: int, token: str, fingerprint: str
) -> ShellyElevateIntegrationClient:
    """Wait until the app accepts the provisioned token; returns a client using it."""
    client = ShellyElevateIntegrationClient(async_get_clientsession(hass), host, port, token, fingerprint)
    deadline = time.monotonic() + TOKEN_TIMEOUT
    while True:
        try:
            await client.get_info()
        except ShellyElevateIntegrationCertificateError:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="certificate_mismatch") from None
        except (ShellyElevateIntegrationAuthError, ShellyElevateIntegrationConnectionError):
            if time.monotonic() > deadline:
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key="token_not_accepted") from None
            await asyncio.sleep(1)
        else:
            return client


def default_dashboard_url(hass: HomeAssistant) -> str | None:
    """HA URL the display should show by default."""
    try:
        return get_url(hass, allow_cloud=False, prefer_external=False)
    except NoURLAvailableError:
        return None
