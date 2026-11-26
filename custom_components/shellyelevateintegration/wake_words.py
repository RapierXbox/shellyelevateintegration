"""microWakeWord models on GitHub that a display can download through Home Assistant."""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
import logging
import re
import time
from typing import Any, TypedDict

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .device import ShellyElevateIntegrationDevice

_LOGGER = logging.getLogger(__name__)

# the same two repos the app's own picker offers
SOURCES = {
    "official": "esphome/micro-wake-word-models",
    "community": "TaterTotterson/Tater-Wake-Words",
}
TREES_URL = "https://api.github.com/repos/{repo}/git/trees/HEAD?recursive=1"
RAW_URL = "https://raw.githubusercontent.com/{repo}/HEAD/{path}"
# one trees call per repo; GitHub allows 60 anonymous api calls an hour
CACHE_SECONDS = 3600
MAX_FILE_BYTES = 2 * 1024 * 1024
VAD_STEM = "vad"
# parts of a model id that are its repo folder, not words of the phrase (like the app's VoiceEngine.phraseOf)
_FOLDER_PART = re.compile(r"(?i)v\d+|models|experiments|microwakewords(v\d+)?")


@dataclass(frozen=True, slots=True)
class CatalogModel:
    """One downloadable model."""

    source: str
    path: str
    """Path of the .tflite in its repo."""
    stem: str
    phrase: str
    has_json: bool


class _Cache(TypedDict, total=False):
    models: list[CatalogModel]
    at: float


_CACHE: HassKey[_Cache] = HassKey(f"{DOMAIN}_wake_word_catalog")


def phrase_of(model_id: str) -> str:
    """okay_nabu_models_v2 or hey_glados_microWakeWordsV6 -> Okay Nabu / Hey Glados."""
    words = [p for p in re.split(r"[_\-\s]+", model_id) if p and not _FOLDER_PART.fullmatch(p)]
    return " ".join(w[:1].upper() + w[1:] for w in words) or model_id


def _folder_version(path: str) -> int:
    """Trailing number of the folder (microWakeWordsV6 -> 6, models/v2 -> 2), 0 without one."""
    folder = path.rpartition("/")[0]
    match = re.search(r"(\d+)$", folder)
    return int(match.group(1)) if match else 0


def parse_tree(source: str, tree: list[dict[str, Any]]) -> list[CatalogModel]:
    """The newest model per stem of one repo tree."""
    paths = {item.get("path", "") for item in tree if item.get("type") == "blob"}
    newest: dict[str, str] = {}
    for path in paths:
        if not path.endswith(".tflite"):
            continue
        stem = path.rpartition("/")[2].removesuffix(".tflite")
        if stem == VAD_STEM:
            continue
        if stem not in newest or _folder_version(path) > _folder_version(newest[stem]):
            newest[stem] = path
    return [
        CatalogModel(
            source=source,
            path=path,
            stem=stem,
            phrase=phrase_of(stem),
            has_json=path.removesuffix(".tflite") + ".json" in paths,
        )
        for stem, path in newest.items()
    ]


async def _fetch_tree(hass: HomeAssistant, repo: str) -> list[dict[str, Any]]:
    session = async_get_clientsession(hass)
    async with session.get(
        TREES_URL.format(repo=repo),
        headers={"Accept": "application/vnd.github+json"},
        timeout=aiohttp.ClientTimeout(total=20),
    ) as resp:
        resp.raise_for_status()
        data = await resp.json()
    return data.get("tree") or []


async def async_get_catalog(hass: HomeAssistant) -> list[CatalogModel]:
    """Both repos, cached for an hour; the last list stays in use while GitHub fails."""
    cache = hass.data.setdefault(_CACHE, _Cache())
    if cache.get("models") is not None and time.monotonic() - cache["at"] < CACHE_SECONDS:
        return cache["models"]
    models: list[CatalogModel] = []
    try:
        for source, repo in SOURCES.items():
            models += parse_tree(source, await _fetch_tree(hass, repo))
    except (aiohttp.ClientError, TimeoutError, OSError) as err:
        if cache.get("models") is not None:
            _LOGGER.debug("Using the cached wake word list, GitHub request failed: %s", err)
            return cache["models"]
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="wake_word_list_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    models.sort(key=lambda m: (m.phrase.casefold(), m.source))
    cache.update({"models": models, "at": time.monotonic()})
    return models


def catalog_as_list(models: list[CatalogModel], installed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Models for the panel, each marked installed when the display has a model with the same phrase."""
    phrases = {phrase_of(str(ww.get("id", ""))).casefold() for ww in installed}
    return [{**asdict(m), "installed": m.phrase.casefold() in phrases} for m in models]


async def _download(hass: HomeAssistant, url: str) -> bytes:
    session = async_get_clientsession(hass)
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
        resp.raise_for_status()
        if (resp.content_length or 0) > MAX_FILE_BYTES:
            raise ValueError("file larger than 2 MB")
        data = await resp.read()
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError("empty file or larger than 2 MB")
    return data


async def async_install(hass: HomeAssistant, device: ShellyElevateIntegrationDevice, source: str, path: str) -> str:
    """Download a catalog model and send it to the display, which installs and selects it. Returns its id."""
    # only paths of the catalog itself, never a url from the panel
    model = next((m for m in await async_get_catalog(hass) if m.source == source and m.path == path), None)
    if model is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="wake_word_unknown",
            translation_placeholders={"model": path},
        )
    repo = SOURCES[source]
    try:
        tflite = await _download(hass, RAW_URL.format(repo=repo, path=model.path))
        json = (
            await _download(hass, RAW_URL.format(repo=repo, path=model.path.removesuffix(".tflite") + ".json"))
            if model.has_json
            else None
        )
    except (aiohttp.ClientError, TimeoutError, OSError, ValueError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="wake_word_download_failed",
            translation_placeholders={"model": model.phrase, "error": str(err)},
        ) from err
    result = await device.async_command(
        "voice.wake_word_upload",
        name=f"{model.stem}.tflite",
        tflite_b64=base64.b64encode(tflite).decode(),
        json_b64=base64.b64encode(json).decode() if json is not None else None,
        activate=True,
    )
    return str((result or {}).get("id", model.stem))
