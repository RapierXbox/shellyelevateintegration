"""Sidebar panel."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.shellyelevateintegration.panel import (
    FRONTEND_DIR,
    PANEL_FILE,
    PANEL_URL,
    async_setup_panel,
)

PANEL = "custom_components.shellyelevateintegration.panel"


async def test_panel_registered(hass: HomeAssistant) -> None:
    """With the frontend the bundle, the icons and an admin panel are registered."""
    hass.config.components.add("frontend")
    hass.http = MagicMock(async_register_static_paths=AsyncMock())
    with (
        patch(f"{PANEL}.frontend.add_extra_js_url") as add_js,
        patch(f"{PANEL}.panel_custom.async_register_panel", AsyncMock()) as register,
    ):
        await async_setup_panel(hass)
    version = json.loads((Path(FRONTEND_DIR).parent / "manifest.json").read_text("utf-8"))["version"]
    assert add_js.call_args.args[1].endswith(f"?v={version}")
    kwargs = register.await_args.kwargs
    assert kwargs["frontend_url_path"] == PANEL_URL
    assert kwargs["require_admin"] is True
    assert kwargs["module_url"].startswith(f"/shellyelevateintegration_static/{PANEL_FILE}?v={version}-")
    assert kwargs["config"] == {"version": version}
    assert len(hass.http.async_register_static_paths.await_args.args[0]) == 2


async def test_no_panel_without_frontend(hass: HomeAssistant) -> None:
    """Without the frontend nothing is registered."""
    with patch(f"{PANEL}.panel_custom.async_register_panel", AsyncMock()) as register:
        await async_setup_panel(hass)
    register.assert_not_awaited()
