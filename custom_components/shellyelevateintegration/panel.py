"""Sidebar panel (fleet, installer, settings, profiles, backups) and the integration's icon set."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PANEL_URL = "shelly-elevate"
STATIC_URL = f"/{DOMAIN}_static"
ICONS_URL = f"/{DOMAIN}_icons"
FRONTEND_DIR = Path(__file__).parent / "frontend"
ICONS_DIR = Path(__file__).parent / "icons"
PANEL_FILE = "shelly-elevate-panel.js"
ICONS_FILE = "shelly-elevate-icons.js"
# Registered by ICONS_FILE (window.customIcons); same glyph as the brand icon.
SIDEBAR_ICON = "shelly-elevate:display"


async def async_setup_panel(hass: HomeAssistant) -> None:
    """Serve the bundle and icon set, and register the admin panel."""
    if "frontend" not in hass.config.components or not (FRONTEND_DIR / PANEL_FILE).is_file():
        return
    manifest = json.loads(
        await hass.async_add_executor_job((Path(__file__).parent / "manifest.json").read_text, "utf-8")
    )
    version = manifest["version"]
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False),
            StaticPathConfig(ICONS_URL, str(ICONS_DIR), cache_headers=False),
        ]
    )
    # Loaded on every page so the sidebar (and any card) can use the shelly-elevate: icons.
    frontend.add_extra_js_url(hass, f"{ICONS_URL}/{ICONS_FILE}?v={version}")
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL,
        webcomponent_name="shelly-elevate-panel",
        sidebar_title="Shelly Elevate",
        sidebar_icon=SIDEBAR_ICON,
        module_url=f"{STATIC_URL}/{PANEL_FILE}?v={version}",
        embed_iframe=False,
        require_admin=True,
        config={"version": version},
    )
