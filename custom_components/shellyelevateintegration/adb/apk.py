"""ShellyElevate app releases from GitHub."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
import time
from typing import Any, TypedDict

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.hass_dict import HassKey

from ..const import APP_REPO, DOMAIN, UPDATE_CHANNEL_BETA

_LOGGER = logging.getLogger(__name__)

CACHE_SECONDS = 3600
MAX_APK_SIZE = 200 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class AppRelease:
    """One app release."""

    version: str
    tag: str
    prerelease: bool
    url: str  # release page
    apk_url: str
    apk_name: str
    sha256: str | None
    notes: str | None
    published: str | None


class _ReleaseCache(TypedDict, total=False):
    releases: list[AppRelease]
    at: float


_CACHE: HassKey[_ReleaseCache] = HassKey(f"{DOMAIN}_release_cache")


def _parse(release: dict[str, Any]) -> AppRelease | None:
    asset = next(
        (a for a in release.get("assets", []) if str(a.get("name", "")).lower().endswith(".apk")),
        None,
    )
    if asset is None:
        return None
    digest = asset.get("digest") or ""
    tag = str(release.get("tag_name", ""))
    return AppRelease(
        version=tag.removeprefix("v"),
        tag=tag,
        prerelease=bool(release.get("prerelease")),
        url=release.get("html_url", ""),
        apk_url=asset["browser_download_url"],
        apk_name=asset["name"],
        sha256=digest.removeprefix("sha256:") if digest.startswith("sha256:") else None,
        notes=release.get("body"),
        published=release.get("published_at"),
    )


async def async_get_releases(hass: HomeAssistant, *, force: bool = False) -> list[AppRelease]:
    """All releases with an APK (newest first), cached for an hour."""
    cache = hass.data.setdefault(_CACHE, _ReleaseCache())
    if not force and cache.get("releases") is not None and time.monotonic() - cache["at"] < CACHE_SECONDS:
        return cache["releases"]
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"https://api.github.com/repos/{APP_REPO}/releases?per_page=20",
            headers={"Accept": "application/vnd.github+json"},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
    except (aiohttp.ClientError, TimeoutError, OSError) as err:
        if cache.get("releases") is not None:
            _LOGGER.debug("Using cached releases, GitHub request failed: %s", err)
            return cache["releases"]
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="release_fetch_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    releases = [r for r in (_parse(item) for item in data if not item.get("draft")) if r is not None]
    cache.update({"releases": releases, "at": time.monotonic()})
    return releases


async def async_latest_release(hass: HomeAssistant, channel: str) -> AppRelease | None:
    """Latest release for a channel (beta includes pre-releases)."""
    for release in await async_get_releases(hass):
        if channel == UPDATE_CHANNEL_BETA or not release.prerelease:
            return release
    return None


async def async_download_apk(hass: HomeAssistant, release: AppRelease) -> bytes:
    """Download and verify an APK."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(release.apk_url, timeout=aiohttp.ClientTimeout(total=300)) as resp:
            resp.raise_for_status()
            if (resp.content_length or 0) > MAX_APK_SIZE:
                raise HomeAssistantError(translation_domain=DOMAIN, translation_key="apk_too_large")
            data = await resp.read()
    except (aiohttp.ClientError, TimeoutError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="apk_download_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    if release.sha256 is not None:
        digest = await hass.async_add_executor_job(lambda: hashlib.sha256(data).hexdigest())
        if digest.lower() != release.sha256.lower():
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="apk_checksum")
    return data


def version_key(version: str | None) -> tuple[int, ...]:
    """Comparable key for `3.YYDDD.HHMM` style versions."""
    if not version:
        return ()
    parts: list[int] = []
    for part in version.removeprefix("v").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)
