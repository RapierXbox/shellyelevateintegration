"""App releases from GitHub and the APK download."""

from __future__ import annotations

from collections.abc import AsyncGenerator
import hashlib
from typing import Any

from aiohttp import ClientError, web
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.shellyelevateintegration.adb.apk import (
    _CACHE,
    MAX_APK_SIZE,
    AppRelease,
    async_download_apk,
    async_get_releases,
    async_latest_release,
    version_key,
)

URL = "https://api.github.com/repos/RapierXbox/ShellyElevate/releases?per_page=20"
APK = b"PK\x03\x04 fake apk"


def _github(
    tag: str, *, prerelease: bool = False, apk: bool = True, draft: bool = False, digest: str | None = None
) -> dict[str, Any]:
    assets = [{"name": "notes.txt", "browser_download_url": "https://x/notes.txt"}]
    if apk:
        asset = {"name": "ShellyElevate.APK", "browser_download_url": f"https://x/{tag}.apk"}
        if digest is not None:
            asset["digest"] = digest
        assets.append(asset)
    return {
        "tag_name": tag,
        "prerelease": prerelease,
        "draft": draft,
        "html_url": f"https://github.com/x/{tag}",
        "body": f"Notes {tag}",
        "published_at": "2026-06-01T00:00:00Z",
        "assets": assets,
    }


@pytest.fixture(autouse=True)
def no_cache(hass: HomeAssistant, release_cache: Any) -> None:
    """Start without cached releases."""
    hass.data.pop(_CACHE)


async def test_releases(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Releases with an APK, newest first, drafts skipped, cached for an hour."""
    aioclient_mock.get(
        URL,
        json=[
            _github("v3.26170.1000", prerelease=True),
            _github("v3.26160.0900", digest="sha256:" + "ab" * 32),
            _github("v3.26150.0100", apk=False),
            _github("v3.26140.0100", draft=True),
            _github("v3.26130.0100", digest="md5:123"),
        ],
    )
    releases = await async_get_releases(hass)
    assert [r.version for r in releases] == ["3.26170.1000", "3.26160.0900", "3.26130.0100"]
    assert releases[1].sha256 == "ab" * 32
    assert releases[1].apk_url == "https://x/v3.26160.0900.apk"
    assert releases[2].sha256 is None
    assert releases[0].notes == "Notes v3.26170.1000"
    assert (await async_latest_release(hass, "beta")).version == "3.26170.1000"
    assert (await async_latest_release(hass, "stable")).version == "3.26160.0900"
    assert aioclient_mock.call_count == 1
    await async_get_releases(hass, force=True)
    assert aioclient_mock.call_count == 2


async def test_releases_errors(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """A failed request uses the cache, or fails without one."""
    aioclient_mock.get(URL, status=403)
    with pytest.raises(HomeAssistantError) as err:
        await async_get_releases(hass)
    assert err.value.translation_key == "release_fetch_failed"

    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, json=[_github("v3.1.1", prerelease=True)])
    assert len(await async_get_releases(hass)) == 1
    assert await async_latest_release(hass, "stable") is None
    aioclient_mock.clear_requests()
    aioclient_mock.get(URL, exc=ClientError("offline"))
    assert len(await async_get_releases(hass, force=True)) == 1


@pytest.fixture
async def apk_server(hass: HomeAssistant, socket_enabled: None) -> AsyncGenerator[str]:
    """A local download server for APKs."""
    app = web.Application()

    async def apk(request: web.Request) -> web.StreamResponse:
        name = request.match_info["name"]
        if name == "big.apk":
            return web.Response(body=b"x", headers={"Content-Length": str(MAX_APK_SIZE + 1)})
        if name == "missing.apk":
            return web.Response(status=404)
        return web.Response(body=APK)

    app.router.add_get("/{name}", apk)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    yield f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"  # type: ignore[union-attr]
    await runner.cleanup()


def _release(url: str, sha256: str | None = None) -> AppRelease:
    return AppRelease("1", "v1", False, "", url, "a.apk", sha256, None, None)


async def test_download(hass: HomeAssistant, apk_server: str) -> None:
    """The APK is checked against its digest and its size."""
    assert await async_download_apk(hass, _release(f"{apk_server}/a.apk")) == APK
    good = hashlib.sha256(APK).hexdigest().upper()
    assert await async_download_apk(hass, _release(f"{apk_server}/a.apk", good)) == APK
    with pytest.raises(HomeAssistantError) as err:
        await async_download_apk(hass, _release(f"{apk_server}/a.apk", "00" * 32))
    assert err.value.translation_key == "apk_checksum"
    with pytest.raises(HomeAssistantError) as err:
        await async_download_apk(hass, _release(f"{apk_server}/missing.apk"))
    assert err.value.translation_key == "apk_download_failed"


async def test_download_too_large(hass: HomeAssistant, apk_server: str) -> None:
    """An APK larger than any real one is refused before it is read."""
    with pytest.raises(HomeAssistantError) as err:
        await async_download_apk(hass, _release(f"{apk_server}/big.apk"))
    assert err.value.translation_key in ("apk_too_large", "apk_download_failed")


def test_version_key() -> None:
    """3.YYDDD.HHMM versions compare numerically."""
    assert version_key("v3.26160.0900") > version_key("3.26150.1200")
    assert version_key("3.26160.0900-beta") == (3, 26160, 900)
    assert version_key("3.x") == (3, 0)
    assert version_key(None) == ()
