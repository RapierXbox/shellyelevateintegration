"""Settings backups and profiles."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.shellyelevateintegration.api import SettingDef, ShellyElevateIntegrationConnectionError
from custom_components.shellyelevateintegration.const import OPT_AUTO_BACKUP
from custom_components.shellyelevateintegration.settings import schema as schema_util
from custom_components.shellyelevateintegration.settings.backups import (
    AUTO_BACKUP_DELAY,
    BackupStore,
    async_get_backup_store,
)
from custom_components.shellyelevateintegration.settings.profiles import (
    STORAGE_KEY as PROFILES_KEY,
    ProfileManager,
    async_get_profile_manager,
)

from ..common import FakeDisplay
from ..const import DEVICE_ID


async def _after(hass: HomeAssistant, seconds: float) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


async def test_store(hass: HomeAssistant) -> None:
    """Snapshots are deduplicated, pruned (named ones last) and deleted."""
    store = await async_get_backup_store(hass)
    assert store is await async_get_backup_store(hass)
    kwargs: dict[str, Any] = {"fw_version": "1", "model": "X", "keep": 3}
    assert store.add("d", {"a": 1}, reason="setup", **kwargs) is not None
    assert store.add("d", {"a": 1}, reason="auto", **kwargs) is None
    named = store.add("d", {"a": 1}, reason="manual", name="Keep me", **kwargs)
    for value in range(2, 5):
        store.add("d", {"a": value}, reason="auto", **kwargs)
    items = store.list("d")
    assert len(items) == 3
    assert named in items
    assert store.get("d")["settings"] == {"a": 4}
    store.delete("d", named["id"])
    with pytest.raises(HomeAssistantError) as err:
        store.get("d", named["id"])
    assert err.value.translation_key == "backup_not_found"
    with pytest.raises(HomeAssistantError):
        store.get("empty")
    for index in range(3):
        store.add("n", {"i": index}, reason="manual", name=f"n{index}", **kwargs)
    store.add("n", {"i": 9}, reason="manual", name="newest", **kwargs)
    assert [item["name"] for item in store.list("n")] == ["newest", "n2", "n1"]
    imported = store.import_backup("d", {"settings": {"b": 2}}, 10)
    assert imported["name"] == "Imported"
    await store._store.async_save({"backups": store.backups})
    loaded = BackupStore(hass)
    await loaded.async_load()
    assert loaded.list("d")[0]["id"] == imported["id"]


async def test_auto_backup(hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay) -> None:
    """A change on the display is backed up a minute later, also when the read fails."""
    device = init_integration.runtime_data
    assert [b["reason"] for b in device.backups.list()] == ["setup"]
    display.client.push({"type": "settings_changed", "changes": {"screenSaverDelay": 90}})
    display.client.push({"type": "settings_changed", "changes": {"screenSaverDelay": 91}})
    await _after(hass, AUTO_BACKUP_DELAY + 1)
    assert [b["reason"] for b in device.backups.list()] == ["auto", "setup"]
    assert device.backups.list()[0]["settings"]["screenSaverDelay"] == 91

    display.settings_error = ShellyElevateIntegrationConnectionError("gone")
    display.client.push({"type": "settings_changed", "changes": {"touchToWake": False}})
    await _after(hass, AUTO_BACKUP_DELAY + 1)
    assert device.backups.list()[0]["reason"] == "auto"


async def test_auto_backup_off(hass: HomeAssistant, display: FakeDisplay, mock_config_entry: MockConfigEntry) -> None:
    """Without automatic backups only manual ones are made; a pending one is dropped on unload."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={OPT_AUTO_BACKUP: False})
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    device = mock_config_entry.runtime_data
    assert device.backups.list() == []
    display.client.push({"type": "settings_changed", "changes": {"screenSaverDelay": 90}})
    await _after(hass, AUTO_BACKUP_DELAY + 1)
    assert device.backups.list() == []

    # a change right before the unload leaves no timer behind
    hass.config_entries.async_update_entry(mock_config_entry, options={OPT_AUTO_BACKUP: True})
    device.backups._on_message({"type": "settings_changed", "changes": {}})
    device.backups.async_stop()
    device.backups.async_stop()


async def test_restore_nothing_to_do(
    hass: HomeAssistant, init_integration: MockConfigEntry, display: FakeDisplay
) -> None:
    """A restore without changes writes nothing."""
    backups = init_integration.runtime_data.backups
    assert await backups.async_restore() == []
    assert display.writes == []
    assert backups.store.list(DEVICE_ID)


async def test_profiles(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Profiles: default handling, lookup by name, deletion."""
    hass_storage[PROFILES_KEY] = {
        "version": 1,
        "key": PROFILES_KEY,
        "data": {"profiles": {"p1": {"name": "Old", "settings": {}}}, "default": "gone"},
    }
    manager = await async_get_profile_manager(hass)
    assert manager is await async_get_profile_manager(hass)
    assert manager.default_profile_id is None
    schema = [SettingDef(key="secretKey", type="string", per_device=True)]
    pid = await manager.async_save_profile("Kitchen", {"a": 1, "secretKey": "x", "mqttDeviceId": "y"}, schema=schema)
    assert manager.profiles[pid]["settings"] == {"a": 1}
    assert manager.default_profile_id == pid  # the first new profile becomes the default
    await manager.async_save_profile("Kitchen", {"a": 2}, profile_id=pid, make_default=False)
    assert manager.default_profile_id is None
    await manager.async_set_default(pid)
    assert manager.find("kitchen") == pid
    assert manager.find(pid) == pid
    with pytest.raises(HomeAssistantError) as err:
        manager.find("nope")
    assert err.value.translation_key == "profile_not_found"
    with pytest.raises(HomeAssistantError):
        await manager.async_set_default("nope")
    assert manager.settings_for_device(pid, None, {"b"}) == {}
    assert [p["name"] for p in manager.as_list()] == ["Kitchen", "Old"]
    await manager.async_delete(pid)
    assert manager.default_profile_id is None
    await manager.async_delete("p1")
    reloaded = ProfileManager(hass)
    await reloaded.async_load()
    assert reloaded.profiles == {}


def test_schema_helpers() -> None:
    """Per-device and secret keys with and without a schema."""
    schema = [
        SettingDef(key="token", type="string", secret=True),
        SettingDef(key="name", type="string", per_device=True),
    ]
    assert "token" in schema_util.secret_keys(schema)
    assert "mqttPassword" in schema_util.secret_keys(None)
    assert schema_util.portable({"name": 1, "a": 2, "mqttDeviceId": 3}, schema) == {"a": 2}
    assert schema_util.redact({"token": "x", "mqttPassword": "", "a": 1}, schema) == {
        "token": "**REDACTED**",
        "mqttPassword": "",
        "a": 1,
    }
    assert schema_util.diff({"a": 1, "b": 2}, {"a": 1, "b": 3, "c": 4}) == [
        {"key": "b", "current": 2, "new": 3},
        {"key": "c", "current": None, "new": 4},
    ]
