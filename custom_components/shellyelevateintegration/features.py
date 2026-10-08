"""Entities and the Bluetooth scanner follow the features switched on on the display.

Every platform builds its entities with `create_entities(device)` from the current settings and
capabilities. The (domain, unique id) pairs of that are the entities the display should have: when a
setting change alters them the entry reloads, and registry entries that are no longer expected are
removed after setup (Home Assistant restores their customizations when they come back).

Which entities exist depends only on values that the user switches on purpose:

* the capabilities of the display (`requires` of the schema and the capabilities themselves),
* `hidden` of the schema,
* `visible_if` conditions on the feature toggles in FEATURE_KEYS.

A `visible_if` condition on any other setting does not decide whether an entity exists, only whether
it is available (see ShellyElevateIntegrationEntity.available). Commands change some settings as a
side effect: `screen.set` writes `automaticBrightness` and `brightness`, `voice.set_config` writes
`voiceWakeEnabled` and `voiceWakeModelName`, `night_mode.set` writes `nightModeEnabled`, the
microphone button writes `voiceAssistantMuted` and the dashboard can write `screenSaverId`. If those
added or removed entities, setting the screen brightness would reload the entry, which drops the
connection, ends voice sessions and deletes entities that automations use.

State keys never decide it either: a v1 display reports the keys of protocol v1 (a missing value is
unknown, not a missing entity), so one snapshot without a key cannot remove an entity.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
import sys
from typing import TYPE_CHECKING, Any, Final

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.debounce import Debouncer
from homeassistant.loader import async_get_integration

from .const import DOMAIN

if TYPE_CHECKING:
    from .device import ShellyElevateIntegrationDevice

_LOGGER = logging.getLogger(__name__)

RELOAD_COOLDOWN = 2
"""Seconds a burst of setting changes is collected before the entities are compared."""

FEATURE_KEYS: Final = frozenset(
    {
        # protocol v1
        "integrationApiEnabled",
        "displayModule",
        "appSwitcherGesture",
        "screenSaver",
        "wakeOnProximity",
        "mediaEnabled",
        "haVoiceEnabled",
        "bleScannerEnabled",
        "mqttEnabled",
        "buttonRelayEnabled",
        "dynamicTempOffsetEnabled",
        "publishSwipeEvents",
        *(f"swInputMode{index}" for index in range(4)),
        # legacy app
        "liteMode",
        "voiceAssistantEnabled",
        "bluetoothProxyEnabled",
    }
)
"""Feature toggles: `visible_if` conditions on these decide which entities exist.

Only settings the user switches on purpose belong here, never one that a command writes as a side
effect (see the module docstring).
"""

SETUP_CAPS: Final = (
    "microphone",
    "voice",
    "bluetooth",
    "speaker",
    "inputs",
    "buttons",
    "relays",
    "optional_relays_from",
    "power_button",
    "proximity",
    "lux",
    "temperature",
    "humidity",
    "dimmer",
    "screenshot",
)
"""Capabilities the setup depends on (platforms, voice, the Bluetooth scanner): a change reloads."""

type EntityKey = tuple[str, str]
"""(entity domain, unique id) of an entity of this integration."""

type BluetoothSetup = Callable[[HomeAssistant, ShellyElevateIntegrationDevice], Callable[[], None]]


def expected_entities(device: ShellyElevateIntegrationDevice, platforms: list[Platform]) -> set[EntityKey] | None:
    """Entities the display should have now, None if a platform module is not loaded."""
    expected: set[EntityKey] = set()
    for platform in platforms:
        # loaded before the platforms are set up so this never imports in the event loop
        module = sys.modules.get(f"{__package__}.{platform.value}")
        if module is None:
            return None
        expected |= {
            (platform.value, entity.unique_id)
            for entity in module.create_entities(device)
            if entity.unique_id is not None
        }
    return expected


def setup_capabilities(device: ShellyElevateIntegrationDevice) -> dict[str, Any]:
    """The capabilities in SETUP_CAPS as the display reports them now."""
    caps = device.info.capabilities.as_dict()
    return {name: caps.get(name) for name in SETUP_CAPS}


class FeatureWatcher:
    """Reloads the entry when the expected entities change and keeps the BLE scanner in sync."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: ShellyElevateIntegrationDevice,
        platforms: list[Platform],
        bluetooth_setup: BluetoothSetup | None,
    ) -> None:
        """Initialize; `bluetooth_setup` is None when the display cannot be a scanner."""
        self.hass = hass
        self.device = device
        self._platforms = platforms
        self._bluetooth_setup = bluetooth_setup
        self._bluetooth_unload: Callable[[], None] | None = None
        self._expected: set[EntityKey] | None = None
        self._setup_caps = setup_capabilities(device)
        self._ready = False
        self._reload_scheduled = False
        self._unsubs: list[Callable[[], None]] = []
        self._debouncer = Debouncer(
            hass, _LOGGER, cooldown=RELOAD_COOLDOWN, immediate=False, function=self._async_check
        )

    async def async_start(self) -> None:
        """Remember the entities the platforms are about to create and listen for setting changes."""
        integration = await async_get_integration(self.hass, DOMAIN)
        await integration.async_get_platforms([platform.value for platform in self._platforms])
        self._unsubs.append(self.device.async_add_message_listener(self._on_message))
        self._expected = expected_entities(self.device, self._platforms)

    @callback
    def async_stop(self) -> None:
        """Stop listening and unregister the scanner."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._debouncer.async_shutdown()
        self._async_set_bluetooth(False)

    @callback
    def async_setup_done(self) -> None:
        """After the platforms: drop the registry entries that are not expected anymore."""
        self._ready = True
        self._async_set_bluetooth(self.device.bluetooth_active)
        expected = expected_entities(self.device, self._platforms)
        if expected is None or self._expected is None:
            return
        if expected != self._expected:
            # a setting changed while the platforms were set up so they may have used either value
            self._debouncer.async_schedule_call()
            return
        self._async_remove_stale(expected)

    # ---------------------------------------------------------------- triggers

    @callback
    def _on_message(self, message: dict[str, object]) -> None:
        # a reconnect reads the settings again and reports the changed ones like this
        if message.get("type") in ("settings_changed", "_info_changed") and self._ready:
            self._debouncer.async_schedule_call()

    async def _async_check(self) -> None:
        entry = self.device.entry
        if self._reload_scheduled or entry.state is not ConfigEntryState.LOADED or entry.setup_lock.locked():
            return
        if not self.device.available:
            return
        if (caps := setup_capabilities(self.device)) != self._setup_caps:
            changed = sorted(name for name in SETUP_CAPS if caps[name] != self._setup_caps[name])
            _LOGGER.info("Reloading %s for changed capabilities: %s", entry.title, ", ".join(changed))
            self._async_reload()
            return
        if not await self.device.async_get_schema() and not self.device.legacy:
            # without the schema the rules are not known for sure
            return
        self._async_set_bluetooth(self.device.bluetooth_active)
        expected = expected_entities(self.device, self._platforms)
        if expected is None or expected == self._expected:
            return
        added = sorted(f"{domain}.{uid}" for domain, uid in expected - (self._expected or set()))
        removed = sorted(f"{domain}.{uid}" for domain, uid in (self._expected or set()) - expected)
        _LOGGER.info(
            "Reloading %s for changed features (new: %s, gone: %s)",
            entry.title,
            ", ".join(added) or "-",
            ", ".join(removed) or "-",
        )
        self._async_reload()

    # ---------------------------------------------------------------- actions

    @callback
    def _async_reload(self) -> None:
        self._reload_scheduled = True
        self.hass.config_entries.async_schedule_reload(self.device.entry.entry_id)

    @callback
    def _async_remove_stale(self, expected: set[EntityKey]) -> None:
        """Remove registry entries of this entry that are not expected anymore."""
        entry_id = self.device.entry.entry_id
        registry = er.async_get(self.hass)
        for reg_entry in er.async_entries_for_config_entry(registry, entry_id):
            if (reg_entry.domain, reg_entry.unique_id) not in expected:
                _LOGGER.debug("Removing %s: its feature is off or missing", reg_entry.entity_id)
                registry.async_remove(reg_entry.entity_id)
        # devices of this entry other than the display itself are left over from an earlier pairing
        devices = dr.async_get(self.hass)
        for device_entry in dr.async_entries_for_config_entry(devices, entry_id):
            if device_entry.id == self.device.device_entry_id:
                continue
            if er.async_entries_for_device(registry, device_entry.id, include_disabled_entities=True):
                continue
            devices.async_update_device(device_entry.id, remove_config_entry_id=entry_id)

    @callback
    def _async_set_bluetooth(self, on: bool) -> None:
        """Register or unregister the display as a remote Bluetooth scanner."""
        if on and self._bluetooth_unload is None and self._bluetooth_setup is not None:
            self._bluetooth_unload = self._bluetooth_setup(self.hass, self.device)
            _LOGGER.debug("%s is a Bluetooth scanner now", self.device.entry.title)
        elif not on and self._bluetooth_unload is not None:
            self._bluetooth_unload()
            self._bluetooth_unload = None
            _LOGGER.debug("%s is no Bluetooth scanner anymore", self.device.entry.title)
