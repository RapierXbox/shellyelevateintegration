"""Config flow for Shelly Elevate."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import instance_id, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import voluptuous as vol

from .api import (
    API_MAJOR,
    DEFAULT_NAME,
    DEFAULT_PORT,
    Capabilities,
    Hello,
    LegacyClient,
    SettingDef,
    ShellyElevateIntegrationApi,
    ShellyElevateIntegrationCertificateError,
    ShellyElevateIntegrationClient,
    ShellyElevateIntegrationConnectionError,
    ShellyElevateIntegrationError,
    ShellyElevateIntegrationPairingError,
    async_pair_confirm,
    async_pair_start,
    async_probe,
    model_name,
    parse_api_version,
)
from .const import (
    CONF_DEVICE_ID,
    CONF_FEATURES_AUTO_ENABLED,
    CONF_FINGERPRINT,
    CONF_LEGACY,
    CONF_MAC,
    CONF_PANEL,
    CONF_TOKEN,
    DEFAULT_BACKUP_KEEP,
    DEFAULT_THERMOSTAT_MAX_TEMP,
    DEFAULT_THERMOSTAT_MIN_TEMP,
    DEFAULT_THERMOSTAT_TOLERANCE,
    DOMAIN,
    OPT_ADB,
    OPT_AUTO_BACKUP,
    OPT_BACKUP_KEEP,
    OPT_RELAYS_AS_LIGHTS,
    OPT_THERMOSTAT,
    OPT_THERMOSTAT_MAX_TEMP,
    OPT_THERMOSTAT_MIN_CYCLE,
    OPT_THERMOSTAT_MIN_TEMP,
    OPT_THERMOSTAT_MODE,
    OPT_THERMOSTAT_RELAY,
    OPT_THERMOSTAT_SENSOR,
    OPT_THERMOSTAT_TOLERANCE,
    OPT_UPDATE_CHANNEL,
    OPT_WATCHDOG,
    PANEL_UNIQUE_ID,
    UPDATE_CHANNEL_BETA,
    UPDATE_CHANNEL_STABLE,
    is_panel_entry,
)
from .settings.profiles import ProfileManager, async_get_profile_manager

_LOGGER = logging.getLogger(__name__)

CONF_CODE = "code"
STOCK_SERVICE_TYPE = "_shelly._tcp.local."
CONF_PROFILE = "profile"
NO_PROFILE = "__none__"


class ShellyElevateIntegrationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize."""
        self._host: str = ""
        self._port: int = DEFAULT_PORT
        self._hello: Hello | None = None
        self._pairing_id: str | None = None
        self._token: str | None = None

    # ---------------------------------------------------------------- entry points

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Add a display, or only the panel (to install ShellyElevate on a new display)."""
        if any(is_panel_entry(entry) for entry in self._async_current_entries(include_ignore=False)):
            return await self.async_step_display()  # the panel is already there
        return self.async_show_menu(step_id="user", menu_options=["display", "panel"])

    async def async_step_panel(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Only the sidebar panel: no display is needed to install ShellyElevate on one."""
        await self.async_set_unique_id(PANEL_UNIQUE_ID, raise_on_progress=False)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Shelly Elevate panel", data={CONF_PANEL: True})

    async def async_step_display(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manual setup of a display by address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST].strip()
            self._port = user_input[CONF_PORT]
            try:
                self._hello = await async_probe(async_get_clientsession(self.hass), self._host, self._port)
            except ShellyElevateIntegrationConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if (error := self._check_api()) is not None:
                    return self.async_abort(reason=error)
                self._port = self._hello.port
                await self.async_set_unique_id(self._hello.device_id)
                self._abort_if_unique_id_configured(updates=self._verified_updates(self._hello))
                return await self._async_after_probe()
        return self.async_show_form(
            step_id="display",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(int, vol.Range(1, 65535)),
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """Discovered via mDNS: a display running ShellyElevate, or a stock Wall Display."""
        if discovery_info.type == STOCK_SERVICE_TYPE:
            return await self._async_wall_display_discovered(discovery_info)
        props = discovery_info.properties
        device_id = props.get("id")
        if not device_id:
            return self.async_abort(reason="not_shellyelevateintegration")
        self._host = discovery_info.host
        self._port = discovery_info.port or DEFAULT_PORT
        await self.async_set_unique_id(device_id)
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, device_id)
        if entry is not None and entry.source != SOURCE_IGNORE:
            return await self._async_known_display_announced(entry)
        self._abort_if_unique_id_configured()
        self._hello = Hello(
            device_id=device_id,
            name=props.get("name") or DEFAULT_NAME,
            model=props.get("model"),
            codename=props.get("codename"),
            fw_version=props.get("fw"),
            api_version=props.get("api"),
            mac=props.get("mac"),
            paired=props.get("paired") == "1",
            legacy=False,
        )
        if (error := self._check_api()) is not None:
            return self.async_abort(reason=error)
        self.context["title_placeholders"] = {"name": self._hello.name}
        return await self.async_step_zeroconf_confirm()

    async def _async_wall_display_discovered(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """A Wall Display announced by its stock Shelly services.

        Only offered while Shelly Elevate is not set up at all: once it is, the panel is there to
        install the app, and displays running ShellyElevate are discovered on their own.
        """
        if self._async_current_entries(include_ignore=False):
            return self.async_abort(reason="already_configured")
        self._host = discovery_info.host
        await self.async_set_unique_id(f"wall-display-{discovery_info.name.split('.')[0].lower()}")
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": "Shelly Wall Display"}
        return await self.async_step_wall_display_confirm()

    async def async_step_wall_display_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Add the display if it runs ShellyElevate already; otherwise add the panel to install it."""
        if user_input is None:
            self._set_confirm_only()
            return self.async_show_form(step_id="wall_display_confirm", description_placeholders={"host": self._host})
        try:
            self._hello = await async_probe(async_get_clientsession(self.hass), self._host)
        except ShellyElevateIntegrationConnectionError:
            # stock app only: the panel's Install tab puts ShellyElevate on it
            return await self.async_step_panel()
        if (error := self._check_api()) is not None:
            return self.async_abort(reason=error)
        self._port = self._hello.port
        await self.async_set_unique_id(self._hello.device_id, raise_on_progress=False)
        self._abort_if_unique_id_configured()
        return await self._async_after_probe()

    async def async_step_system(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Created by the integration itself: keep the panel when the last display is removed."""
        return await self.async_step_panel()

    async def async_step_zeroconf_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm a discovered display."""
        assert self._hello is not None
        if user_input is not None:
            return await self.async_step_pair()
        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders=self._placeholders(),
        )

    async def _async_known_display_announced(self, entry: ConfigEntry) -> ConfigFlowResult:
        """A configured display was announced, maybe at a new address.

        mDNS is unauthenticated: anyone can announce a display's id. A paired entry only moves
        when the new address presents the pinned certificate (the TLS handshake proves the
        display's private key), so its token is never sent to whoever announced it.
        """
        if not entry.data.get(CONF_TOKEN):
            # Legacy entry: it cannot be verified (no certificate), and HA writes settings to it,
            # profiles with secrets included. Never move it on an announcement; an update of the
            # app is detected by the legacy client itself, a new address needs Reconfigure.
            return self.async_abort(reason="already_configured")
        if (entry.data[CONF_HOST], entry.data.get(CONF_PORT, DEFAULT_PORT)) == (self._host, self._port):
            return self.async_abort(reason="already_configured")
        if entry.state is ConfigEntryState.LOADED and entry.runtime_data.available:
            return self.async_abort(reason="already_configured")
        try:
            hello = await async_probe(async_get_clientsession(self.hass), self._host, self._port)
        except ShellyElevateIntegrationConnectionError:
            return self.async_abort(reason="cannot_connect")
        if hello.device_id != entry.unique_id:
            return self.async_abort(reason="already_configured")
        self._abort_if_unique_id_configured(updates=self._verified_updates(hello))
        return self.async_abort(reason="already_configured")  # not reached: the entry exists

    def _verified_updates(self, hello: Hello) -> dict[str, Any]:
        """Address changes that are safe to apply to the configured entry for `hello`'s display."""
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, hello.device_id)
        if entry is None or entry.source == SOURCE_IGNORE:
            return {}
        if entry.data.get(CONF_LEGACY):
            return {CONF_HOST: self._host, CONF_PORT: hello.port} if hello.legacy else {}
        pinned = entry.data.get(CONF_FINGERPRINT)
        if hello.legacy or not pinned or hello.fingerprint != pinned:
            _LOGGER.warning("Not moving %s to %s: it does not present the paired certificate", entry.title, self._host)
            return {}
        return {CONF_HOST: self._host, CONF_PORT: hello.port}

    async def async_step_installer(self, discovery_info: dict[str, Any]) -> ConfigFlowResult:
        """Started by the installer after it provisioned a token over ADB."""
        self._host = discovery_info[CONF_HOST]
        self._port = discovery_info.get(CONF_PORT, DEFAULT_PORT)
        self._token = discovery_info.get(CONF_TOKEN)
        try:
            self._hello = await async_probe(async_get_clientsession(self.hass), self._host, self._port)
        except ShellyElevateIntegrationConnectionError:
            return self.async_abort(reason="cannot_connect")
        if not self._hello.legacy:
            if not self._token:
                return self.async_abort(reason="cannot_connect")
            if self._hello.fingerprint != discovery_info.get(CONF_FINGERPRINT):
                return self.async_abort(reason="certificate_mismatch")
        self._port = self._hello.port
        ignored = self.hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, self._hello.device_id)
        if ignored is not None and ignored.source == SOURCE_IGNORE:
            # The user installed it on purpose, so "ignore" no longer applies.
            await self.hass.config_entries.async_remove(ignored.entry_id)
        # An open discovery flow for this display is aborted once the entry is created.
        await self.async_set_unique_id(self._hello.device_id, raise_on_progress=False)
        updates: dict[str, Any] = {CONF_HOST: self._host, CONF_PORT: self._port}
        if self._token:
            # Verified over ADB, so it replaces the stored token and certificate.
            updates |= {CONF_TOKEN: self._token, CONF_FINGERPRINT: self._hello.fingerprint, CONF_LEGACY: False}
        self._abort_if_unique_id_configured(updates=updates)
        if profile_id := discovery_info.get(CONF_PROFILE):
            await self._async_apply_profile(profile_id)
        return self._async_create()

    # ---------------------------------------------------------------- shared steps

    async def _async_after_probe(self) -> ConfigFlowResult:
        assert self._hello is not None
        if self._hello.legacy:
            return await self.async_step_legacy_confirm()
        return await self.async_step_pair()

    async def async_step_legacy_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Warn that the legacy app has no authentication and limited features."""
        if user_input is not None:
            return await self.async_step_profile()
        return self.async_show_form(step_id="legacy_confirm", description_placeholders=self._placeholders())

    async def async_step_pair(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the code from the display."""
        errors: dict[str, str] = {}
        session = async_get_clientsession(self.hass)
        if (abort := await self._async_ensure_fingerprint()) is not None:
            return abort
        assert self._hello is not None and self._hello.fingerprint is not None
        fingerprint = self._hello.fingerprint
        if user_input is not None and self._pairing_id is not None:
            try:
                self._token = await async_pair_confirm(
                    session, self._host, self._port, self._pairing_id, user_input[CONF_CODE], fingerprint=fingerprint
                )
            except ShellyElevateIntegrationCertificateError:
                return self.async_abort(reason="certificate_mismatch")
            except ShellyElevateIntegrationPairingError as err:
                if err.code == "expired":
                    self._pairing_id = None
                    errors["base"] = "pairing_expired"
                elif err.code == "rate_limited":
                    errors["base"] = "rate_limited"
                else:
                    errors[CONF_CODE] = "invalid_code"
            except ShellyElevateIntegrationConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if self.source == SOURCE_REAUTH:
                    return self._async_finish_reauth()
                return await self.async_step_profile()
        if self._pairing_id is None:
            try:
                self._pairing_id = await async_pair_start(
                    session,
                    self._host,
                    self._port,
                    await instance_id.async_get(self.hass),
                    self._client_name(),
                    fingerprint=fingerprint,
                )
            except ShellyElevateIntegrationCertificateError:
                return self.async_abort(reason="certificate_mismatch")
            except ShellyElevateIntegrationPairingError as err:
                return self.async_abort(reason="rate_limited" if err.code == "rate_limited" else "cannot_connect")
            except ShellyElevateIntegrationError:
                return self.async_abort(reason="cannot_connect")
        return self.async_show_form(
            step_id="pair",
            data_schema=vol.Schema({vol.Required(CONF_CODE): str}),
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    async def _async_ensure_fingerprint(self) -> ConfigFlowResult | None:
        """Discovery only knows the TXT record; fetch the certificate before pairing."""
        assert self._hello is not None
        if self._hello.fingerprint is not None:
            return None
        try:
            hello = await async_probe(async_get_clientsession(self.hass), self._host, self._port)
        except ShellyElevateIntegrationConnectionError:
            return self.async_abort(reason="cannot_connect")
        if hello.legacy or hello.device_id != self._hello.device_id:
            return self.async_abort(reason="wrong_device")
        self._hello, self._port = hello, hello.port
        return None

    async def async_step_profile(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Optionally apply a settings profile to the new display."""
        manager = await async_get_profile_manager(self.hass)
        profiles = manager.profiles
        if not profiles:
            return self._async_create()
        if user_input is not None:
            if (profile_id := user_input[CONF_PROFILE]) != NO_PROFILE:
                try:
                    await self._async_apply_profile(profile_id)
                except ShellyElevateIntegrationError:
                    return self.async_show_form(
                        step_id="profile",
                        data_schema=self._profile_schema(manager),
                        errors={"base": "profile_failed"},
                    )
            return self._async_create()
        return self.async_show_form(step_id="profile", data_schema=self._profile_schema(manager))

    def _profile_schema(self, manager: ProfileManager) -> vol.Schema:
        options = [selector.SelectOptionDict(value=NO_PROFILE, label="—")] + [
            selector.SelectOptionDict(value=pid, label=p["name"]) for pid, p in manager.profiles.items()
        ]
        return vol.Schema(
            {
                vol.Required(CONF_PROFILE, default=manager.default_profile_id or NO_PROFILE): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN)
                )
            }
        )

    async def _async_apply_profile(self, profile_id: str) -> None:
        assert self._hello is not None
        manager = await async_get_profile_manager(self.hass)
        session = async_get_clientsession(self.hass)
        client: ShellyElevateIntegrationApi
        if self._hello.legacy:
            client = LegacyClient(session, self._host, self._port, self._hello.device_id)
        else:
            client = ShellyElevateIntegrationClient(
                session, self._host, self._port, self._token or "", self._hello.fingerprint
            )
        # only keys this display knows like services.async_profile_diff
        known = set(await client.get_settings())
        schema: list[SettingDef] | None = None
        if not self._hello.legacy:
            try:
                schema = await client.get_settings_schema()
            except ShellyElevateIntegrationError as err:
                _LOGGER.debug("Could not fetch the settings schema of %s: %s", self._host, err)
            if schema:
                known &= {item.key for item in schema}
        changes = manager.settings_for_device(profile_id, schema, known)
        if changes:
            await client.set_settings(changes)

    # ---------------------------------------------------------------- reauth / reconfigure

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Token rejected, or a legacy display was updated to API v1: pair (again)."""
        self._host = entry_data[CONF_HOST]
        self._port = entry_data.get(CONF_PORT, DEFAULT_PORT)
        try:
            self._hello = await async_probe(async_get_clientsession(self.hass), self._host, self._port)
        except ShellyElevateIntegrationConnectionError:
            return self.async_abort(reason="cannot_connect")
        self._port = self._hello.port
        await self.async_set_unique_id(self._hello.device_id)
        self._abort_if_unique_id_mismatch(reason="wrong_device")
        if self._hello.legacy:
            # The legacy app has no pairing; nothing to re-authenticate.
            return self.async_abort(reason="not_upgraded")
        if (error := self._check_api()) is not None:
            return self.async_abort(reason=error)
        if entry_data.get(CONF_LEGACY):
            return await self.async_step_upgrade_confirm()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm re-pairing."""
        if user_input is not None:
            return await self.async_step_pair()
        return self.async_show_form(step_id="reauth_confirm", description_placeholders=self._placeholders())

    async def async_step_upgrade_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Confirm pairing a display that was updated from the legacy app."""
        if user_input is not None:
            return await self.async_step_pair()
        return self.async_show_form(step_id="upgrade_confirm", description_placeholders=self._placeholders())

    @callback
    def _async_finish_reauth(self) -> ConfigFlowResult:
        assert self._hello is not None
        entry = self._get_reauth_entry()
        updates = {CONF_TOKEN: self._token, CONF_FINGERPRINT: self._hello.fingerprint, CONF_PORT: self._port}
        if not entry.data.get(CONF_LEGACY):
            return self.async_update_reload_and_abort(entry, data_updates=updates)
        return self.async_update_reload_and_abort(
            entry,
            data_updates={**updates, CONF_LEGACY: False, CONF_MAC: self._hello.mac},
            reason="upgrade_successful",
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change host / port."""
        entry = self._get_reconfigure_entry()
        if is_panel_entry(entry):
            return self.async_abort(reason="panel_entry")
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                hello = await async_probe(
                    async_get_clientsession(self.hass), user_input[CONF_HOST], user_input[CONF_PORT]
                )
            except ShellyElevateIntegrationConnectionError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(hello.device_id)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                self._host = user_input[CONF_HOST]
                if entry.data.get(CONF_LEGACY) and not hello.legacy:
                    # Updated app at the new address: move the legacy entry; the legacy client
                    # then detects the update and asks to pair (upgrade flow).
                    return self.async_update_reload_and_abort(entry, data_updates={CONF_HOST: self._host})
                if not (updates := self._verified_updates(hello)):
                    # A different certificate (or app generation) needs pairing, not just a new address.
                    return self.async_abort(reason="certificate_mismatch")
                return self.async_update_reload_and_abort(entry, data_updates=updates)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_PORT): vol.All(int, vol.Range(1, 65535)),
                    }
                ),
                user_input or entry.data,
            ),
            errors=errors,
        )

    # ---------------------------------------------------------------- helpers

    def _check_api(self) -> str | None:
        assert self._hello is not None
        if self._hello.legacy:
            return None
        major, _ = parse_api_version(self._hello.api_version)
        if major != API_MAJOR:
            return "incompatible_api"
        return None

    def _client_name(self) -> str:
        return f"Home Assistant ({self.hass.config.location_name})"

    def _placeholders(self) -> dict[str, str]:
        assert self._hello is not None
        return {
            "name": self._hello.name,
            "model": model_name(self._hello.codename, self._hello.model),
            "host": self._host,
        }

    @callback
    def _async_create(self) -> ConfigFlowResult:
        assert self._hello is not None
        data = {
            CONF_HOST: self._host,
            CONF_PORT: self._port,
            CONF_DEVICE_ID: self._hello.device_id,
            CONF_LEGACY: self._hello.legacy,
            CONF_TOKEN: self._token,
            CONF_FINGERPRINT: self._hello.fingerprint,
            CONF_MAC: self._hello.mac,
            # media bluetooth and voice are turned on once on the first setup
            CONF_FEATURES_AUTO_ENABLED: False,
        }
        return self.async_create_entry(title=self._hello.name, data=data)

    @classmethod
    @callback
    def async_supports_options(cls, config_entry: ConfigEntry) -> bool:
        """The panel-only entry has no options."""
        return not is_panel_entry(config_entry)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ShellyElevateIntegrationOptionsFlow:
        """Options flow."""
        return ShellyElevateIntegrationOptionsFlow()


class ShellyElevateIntegrationOptionsFlow(OptionsFlowWithReload):
    """Integration options (general, then the thermostat if enabled)."""

    def __init__(self) -> None:
        """Initialize."""
        self._options: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """General options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._options = {**self.config_entry.options, **user_input}
            if not user_input.get(OPT_THERMOSTAT):
                return self.async_create_entry(data=self._options)
            if (caps := self._capabilities()) is not None and caps.relays == 0:
                errors[OPT_THERMOSTAT] = "no_relays"  # e.g. the Wall Display D1
            else:
                return await self.async_step_thermostat()
        loaded = self.config_entry.state is ConfigEntryState.LOADED
        schema = vol.Schema(
            {
                vol.Required(OPT_RELAYS_AS_LIGHTS, default=False): bool,
                vol.Required(OPT_THERMOSTAT, default=False): bool,
                vol.Required(OPT_AUTO_BACKUP, default=True): bool,
                vol.Required(OPT_BACKUP_KEEP, default=DEFAULT_BACKUP_KEEP): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=100, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required(OPT_UPDATE_CHANNEL, default=UPDATE_CHANNEL_STABLE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[UPDATE_CHANNEL_STABLE, UPDATE_CHANNEL_BETA],
                        translation_key=OPT_UPDATE_CHANNEL,
                    )
                ),
                vol.Required(
                    OPT_ADB,
                    default=bool(self.config_entry.runtime_data.settings.get("adbWifiEnabled")) if loaded else False,
                ): bool,
                vol.Required(OPT_WATCHDOG, default=False): bool,
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or self.config_entry.options),
            errors=errors,
        )

    def _capabilities(self) -> Capabilities | None:
        """The display's capabilities, if it is connected."""
        if self.config_entry.state is ConfigEntryState.LOADED:
            return self.config_entry.runtime_data.info.capabilities
        return None

    async def async_step_thermostat(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Thermostat: relay, temperature source and regulation."""
        errors: dict[str, str] = {}
        if user_input is not None:
            caps = self._capabilities()
            if user_input[OPT_THERMOSTAT_MIN_TEMP] >= user_input[OPT_THERMOSTAT_MAX_TEMP]:
                errors["base"] = "invalid_temp_range"
            elif not user_input.get(OPT_THERMOSTAT_SENSOR) and caps is not None and not caps.temperature:
                # XL, X2i and X1i have no temperature sensor of their own
                errors[OPT_THERMOSTAT_SENSOR] = "sensor_required"
            else:
                options = {**self._options, **user_input}
                if not user_input.get(OPT_THERMOSTAT_SENSOR):
                    # empty = the display's own temperature sensor
                    options.pop(OPT_THERMOSTAT_SENSOR, None)
                return self.async_create_entry(data=options)
        relays = 2
        if self.config_entry.state is ConfigEntryState.LOADED:
            relays = max(1, self.config_entry.runtime_data.info.capabilities.relays)
        schema = vol.Schema(
            {
                vol.Required(OPT_THERMOSTAT_RELAY, default="0"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=str(idx), label=f"{idx + 1}") for idx in range(relays)
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(OPT_THERMOSTAT_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Required(OPT_THERMOSTAT_MODE, default="heat"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["heat", "cool"], translation_key=OPT_THERMOSTAT_MODE)
                ),
                vol.Required(OPT_THERMOSTAT_TOLERANCE, default=DEFAULT_THERMOSTAT_TOLERANCE): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1, max=3, step=0.1, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(OPT_THERMOSTAT_MIN_CYCLE, default=0): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=3600, step=10, unit_of_measurement="s", mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(OPT_THERMOSTAT_MIN_TEMP, default=DEFAULT_THERMOSTAT_MIN_TEMP): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-10, max=40, step=0.5, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(OPT_THERMOSTAT_MAX_TEMP, default=DEFAULT_THERMOSTAT_MAX_TEMP): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=50, step=0.5, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="thermostat",
            data_schema=self.add_suggested_values_to_schema(schema, self.config_entry.options),
            errors=errors,
        )
