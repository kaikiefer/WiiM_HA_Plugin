"""WiiM playback via the official local HTTP API."""

import math

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.components.media_player import (
    MediaPlayerEntityFeature as Feature,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .api import WiiMError, number
from .const import SOURCES
from .entity import WiiMEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([WiiMMediaPlayer(entry.runtime_data)])


class WiiMMediaPlayer(WiiMEntity, MediaPlayerEntity):
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_supported_features = (
        Feature.PLAY
        | Feature.PAUSE
        | Feature.STOP
        | Feature.NEXT_TRACK
        | Feature.PREVIOUS_TRACK
        | Feature.VOLUME_SET
        | Feature.VOLUME_MUTE
        | Feature.PLAY_MEDIA
        | Feature.SELECT_SOURCE
        | Feature.SEEK
    )

    def __init__(self, coordinator):
        super().__init__(coordinator, "player")
        self._sources = dict(SOURCES)
        # The Mini has an optical output, not an optical input.
        project = str(coordinator.info.get("project", "")).lower()
        if "pro" in project or "ultra" in project or "amp" in project:
            self._sources["Optical In"] = "optical"

    @property
    def player(self):
        return self.coordinator.data["player"]

    @property
    def metadata(self):
        return self.coordinator.data["metadata"]

    @property
    def state(self):
        return {
            "play": MediaPlayerState.PLAYING,
            "pause": MediaPlayerState.PAUSED,
            "stop": MediaPlayerState.IDLE,
            "none": MediaPlayerState.IDLE,
            "loading": MediaPlayerState.BUFFERING,
        }.get(self.player.get("status"))

    @property
    def volume_level(self):
        value = number(self.player.get("vol"))
        return max(0, min(1, value / 100)) if value is not None else None

    @property
    def is_volume_muted(self):
        value = str(self.player.get("mute", ""))
        return value == "1" if value in {"0", "1"} else None

    @property
    def source_list(self):
        return list(self._sources)

    @property
    def source(self):
        mode = str(self.player.get("mode", ""))
        return {
            "1": "AirPlay",
            "2": "DLNA",
            "10": "Wi-Fi",
            "31": "Spotify Connect",
            "32": "TIDAL Connect",
            "40": "Aux In",
            "41": "Bluetooth",
            "43": "Optical In",
            "99": "Group follower",
        }.get(mode)

    @property
    def media_title(self):
        return self.metadata.get("title") or None

    @property
    def media_artist(self):
        return self.metadata.get("artist") or None

    @property
    def media_album_name(self):
        return self.metadata.get("album") or None

    @property
    def media_image_url(self):
        url = self.metadata.get("albumArtURI")
        return (
            url
            if isinstance(url, str) and url.startswith(("http://", "https://"))
            else None
        )

    @property
    def media_content_type(self):
        return MediaType.MUSIC

    @property
    def media_duration(self):
        value = number(self.player.get("totlen"))
        return value / 1000 if value is not None and value > 0 else None

    @property
    def media_position(self):
        value = number(self.player.get("curpos"))
        return value / 1000 if value is not None and value >= 0 else None

    @property
    def media_position_updated_at(self):
        return self.coordinator.updated_at

    async def async_media_play(self):
        await self.command("setPlayerCmd:resume")

    async def async_media_pause(self):
        await self.command("setPlayerCmd:pause")

    async def async_media_stop(self):
        await self.command("setPlayerCmd:stop")

    async def async_media_next_track(self):
        await self.command("setPlayerCmd:next")

    async def async_media_previous_track(self):
        await self.command("setPlayerCmd:prev")

    async def async_set_volume_level(self, volume):
        if not math.isfinite(volume) or not 0 <= volume <= 1:
            raise ServiceValidationError("Volume must be between 0 and 1")
        await self.command(f"setPlayerCmd:vol:{round(volume * 100)}")

    async def async_mute_volume(self, mute):
        await self.command(f"setPlayerCmd:mute:{int(mute)}")

    async def async_media_seek(self, position):
        if not math.isfinite(position) or position < 0:
            raise ServiceValidationError("Seek position must be nonnegative")
        if self.media_duration is not None:
            position = min(position, self.media_duration)
        await self.command(f"setPlayerCmd:seek:{int(position)}")

    async def async_select_source(self, source):
        if source not in self._sources:
            raise ServiceValidationError("Unsupported WiiM input")
        await self.command(f"setPlayerCmd:switchmode:{self._sources[source]}")

    async def async_play_media(self, media_type, media_id, **kwargs):
        if kwargs.get("enqueue"):
            raise ServiceValidationError("Queueing is not supported")
        if media_source.is_media_source_id(media_id):
            resolved = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = resolved.url
        media_id = async_process_play_media_url(self.hass, media_id)
        try:
            await self.coordinator.client.play_url(media_id)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        except WiiMError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()
