"""Media player for the display speaker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
    async_process_play_media_url,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import MediaStatus
from .device import ShellyElevateIntegrationConfigEntry, ShellyElevateIntegrationDevice
from .entity import ShellyElevateIntegrationEntity, ShellyElevateIntegrationEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ShellyElevateIntegrationMediaPlayerDescription(
    ShellyElevateIntegrationEntityDescription, MediaPlayerEntityDescription
):
    """Media player description."""


STATE_MAP = {
    "idle": MediaPlayerState.IDLE,
    "buffering": MediaPlayerState.BUFFERING,
    "playing": MediaPlayerState.PLAYING,
    "paused": MediaPlayerState.PAUSED,
}

LEGACY_FEATURES = (
    MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.MEDIA_ANNOUNCE
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
)
V1_FEATURES = (
    LEGACY_FEATURES
    | MediaPlayerEntityFeature.MEDIA_ENQUEUE
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.NEXT_TRACK
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ShellyElevateIntegrationConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Set up the media player."""
    device = entry.runtime_data
    if device.info.capabilities.speaker:
        async_add_entities([ShellyElevateIntegrationMediaPlayer(device)])


class ShellyElevateIntegrationMediaPlayer(ShellyElevateIntegrationEntity, MediaPlayerEntity):
    """The display speaker.

    With protocol v1 the state comes from `media_status` pushes. The legacy app has no
    readback, so the legacy client tracks state optimistically.
    """

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_name = None
    _attr_media_content_type = MediaType.MUSIC

    def __init__(self, device: ShellyElevateIntegrationDevice) -> None:
        """Initialize."""
        super().__init__(device, ShellyElevateIntegrationMediaPlayerDescription(key="media_player", state_keys=()))
        self._attr_supported_features = LEGACY_FEATURES if device.legacy else V1_FEATURES
        self._position_updated_at: datetime | None = None
        self._last_position: float | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to media status."""
        await super().async_added_to_hass()
        self.async_on_remove(self.device.async_add_message_listener(self._on_message))

    @callback
    def _on_message(self, message: dict[str, Any]) -> None:
        if message.get("type") == "media_status":
            position = self._media.position
            if position != self._last_position:
                self._last_position = position
                self._position_updated_at = dt_util.utcnow() if position is not None else None
            self.async_write_ha_state()
        elif message.get("type") == "settings_changed" and "mediaEnabled" in (message.get("changes") or {}):
            self.async_write_ha_state()

    @property
    def _media(self) -> MediaStatus:
        return self.device.client.media

    @property
    def available(self) -> bool:
        """Legacy app: playback must be enabled in the settings."""
        if not super().available:
            return False
        return not self.device.legacy or bool(self.device.settings.get("mediaEnabled", True))

    @property
    def state(self) -> MediaPlayerState:
        """Playback state."""
        return STATE_MAP.get(self._media.state, MediaPlayerState.IDLE)

    @property
    def volume_level(self) -> float | None:
        """Volume 0..1."""
        return self._media.volume

    @property
    def is_volume_muted(self) -> bool | None:
        """Muted."""
        return None if self.device.legacy else self._media.muted

    @property
    def media_content_id(self) -> str | None:
        """URL."""
        return self._media.url

    @property
    def media_title(self) -> str | None:
        """Title."""
        return self._media.title

    @property
    def media_artist(self) -> str | None:
        """Artist."""
        return self._media.artist

    @property
    def media_album_name(self) -> str | None:
        """Album."""
        return self._media.album

    @property
    def media_image_url(self) -> str | None:
        """Artwork."""
        return self._media.artwork

    @property
    def media_duration(self) -> int | None:
        """Duration in seconds."""
        return None if self._media.duration is None else int(self._media.duration)

    @property
    def media_position(self) -> int | None:
        """Position in seconds."""
        return None if self._media.position is None else int(self._media.position)

    @property
    def media_position_updated_at(self) -> datetime | None:
        """When the position was reported."""
        return self._position_updated_at

    @property
    def repeat(self) -> RepeatMode | None:
        """Repeat mode."""
        if self.device.legacy:
            return None
        try:
            return RepeatMode(self._media.repeat)
        except ValueError:
            return RepeatMode.OFF

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        announce: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Play a URL or media source item; announcements interrupt and resume music."""
        title: str | None = None
        if media_source.is_media_source_id(media_id):
            item = await media_source.async_resolve_media(self.hass, media_id, self.entity_id)
            media_id = item.url
            title = getattr(item, "title", None)
        media_id = async_process_play_media_url(self.hass, media_id)
        extra = kwargs.get("extra") or {}
        params: dict[str, Any] = {
            "url": media_id,
            "channel": "announce" if announce else "music",
            "title": extra.get("title") or title,
        }
        if extra.get("artist"):
            params["artist"] = extra["artist"]
        if extra.get("thumb"):
            params["artwork"] = extra["thumb"]
        if enqueue is not None and not self.device.legacy and not announce:
            params["enqueue"] = str(enqueue)
        await self.device.async_command("media.play", **params)

    async def async_browse_media(
        self, media_content_type: MediaType | str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        """Browse audio media sources."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

    async def async_media_pause(self) -> None:
        """Pause."""
        await self.device.async_command("media.pause")

    async def async_media_play(self) -> None:
        """Resume."""
        await self.device.async_command("media.resume")

    async def async_media_stop(self) -> None:
        """Stop."""
        await self.device.async_command("media.stop")

    async def async_media_next_track(self) -> None:
        """Next item in the queue."""
        await self.device.async_command("media.next")

    async def async_media_seek(self, position: float) -> None:
        """Seek."""
        await self.device.async_command("media.seek", position=position)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume."""
        await self.device.async_command("media.volume", volume=round(volume, 3))

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute."""
        await self.device.async_command("media.volume", muted=mute)

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Repeat mode."""
        await self.device.async_command("media.repeat", mode=str(repeat))
