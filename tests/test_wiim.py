import json
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from aioresponses import aioresponses
from homeassistant.components.media_player import MediaPlayerState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.wiim_local.api import (
    WiiMClient,
    WiiMError,
    number,
    validate_host,
)
from custom_components.wiim_local.button import WiiMPreset
from custom_components.wiim_local.coordinator import WiiMCoordinator
from custom_components.wiim_local.media_player import WiiMMediaPlayer

BASE = "https://192.168.1.5/httpapi.asp"


@pytest.mark.parametrize(
    "host",
    [
        "https://example.com",
        "user@host",
        "host/path",
        "host:80",
        "",
        "-bad",
        "host?x=1",
    ],
)
def test_bad_host(host):
    with pytest.raises(ValueError):
        validate_host(host)


@pytest.mark.parametrize("host", ["192.168.1.5", "wiim.local", "::1"])
def test_host(host):
    assert validate_host(host) == host


async def test_api_encoding_and_ack():
    async with aiohttp.ClientSession() as session:
        client = WiiMClient(session, "192.168.1.5")
        with aioresponses() as mock:
            url = "https://radio.example/stream?a=1&b=hello%20world"
            from yarl import URL

            target = URL(BASE).with_query(command=f"setPlayerCmd:play:{url}")
            mock.get(target, body="OK")
            await client.play_url(url)
            request = next(iter(mock.requests.values()))[0]
            assert request.kwargs["ssl"] is True
            assert request.kwargs["allow_redirects"] is False


@pytest.mark.parametrize(
    "body", ["Failed", '{"status":"Failed"}', "[]", "{}", "not json"]
)
async def test_bad_info(body):
    async with aiohttp.ClientSession() as session:
        with aioresponses() as mock:
            mock.get(BASE + "?command=getStatusEx", body=body)
            with pytest.raises(WiiMError):
                await WiiMClient(session, "192.168.1.5").info()


async def test_network_failure():
    async with aiohttp.ClientSession() as session:
        with aioresponses() as mock:
            mock.get(BASE + "?command=getPlayerStatus", exception=TimeoutError())
            with pytest.raises(WiiMError):
                await WiiMClient(session, "192.168.1.5").player()


async def test_invalid_media():
    client = WiiMClient(MagicMock(), "wiim.local")
    with pytest.raises(ValueError):
        await client.play_url("file:///secret")


def coordinator():
    co = MagicMock()
    co.info = {"uuid": "ABC", "project": "Muzo_Mini", "DeviceName": "Office"}
    co.data = {
        "player": {
            "status": "play",
            "vol": "39",
            "mute": "0",
            "curpos": "12000",
            "totlen": "100000",
        },
        "metadata": {"title": "Track"},
    }
    co.client.request = AsyncMock(return_value="OK")
    co.async_request_refresh = AsyncMock()
    co.last_update_success = True
    return co


async def test_entity_controls_and_units():
    co = coordinator()
    entity = WiiMMediaPlayer(co)
    assert entity.state == MediaPlayerState.PLAYING
    assert entity.volume_level == 0.39
    assert entity.media_position == 12
    assert entity.media_duration == 100
    assert entity.media_title == "Track"
    assert "Optical In" not in entity.source_list
    await entity.async_set_volume_level(0.42)
    co.client.request.assert_awaited_with("setPlayerCmd:vol:42")
    await entity.async_media_seek(30.5)
    co.client.request.assert_awaited_with("setPlayerCmd:seek:30")
    await entity.async_select_source("Aux In")
    co.client.request.assert_awaited_with("setPlayerCmd:switchmode:line-in")
    with pytest.raises(ServiceValidationError):
        await entity.async_select_source("Optical In")
    with pytest.raises(ServiceValidationError):
        await entity.async_set_volume_level(float("nan"))
    await WiiMPreset(co, 12).async_press()
    co.client.request.assert_awaited_with("MCUKeyShortClick:12")
    co.client.request.side_effect = WiiMError("failed")
    with pytest.raises(HomeAssistantError):
        await entity.async_media_pause()


async def test_optional_metadata_and_poll_failure():
    co = WiiMCoordinator.__new__(WiiMCoordinator)
    co.info = {"uuid": "ABC"}
    co.client = MagicMock()
    co.client.player = AsyncMock(return_value={"status": "play"})
    co.client.request = AsyncMock(side_effect=WiiMError("unsupported"))
    data = await co._async_update_data()
    assert data["metadata"] == {}
    co.client.player.side_effect = WiiMError("offline")
    with pytest.raises(UpdateFailed):
        await co._async_update_data()


def test_number_and_manifest():
    assert number("nan") is None
    assert number("broken") is None
    with open("custom_components/wiim_local/manifest.json") as manifest_file:
        manifest = json.load(manifest_file)
    assert manifest["config_flow"]
    assert manifest["domain"] == "wiim_local"


async def test_config_flow_success_and_duplicate():
    from unittest.mock import patch

    from custom_components.wiim_local.config_flow import WiiMConfigFlow

    flow = WiiMConfigFlow()
    flow.hass = MagicMock()
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    client = MagicMock()
    client.info = AsyncMock(return_value={"uuid": "ABC", "DeviceName": "Office"})
    client.player = AsyncMock(return_value={"status": "stop"})
    with (
        patch(
            "custom_components.wiim_local.config_flow.WiiMClient", return_value=client
        ),
        patch("custom_components.wiim_local.config_flow.async_get_clientsession"),
    ):
        result = await flow.async_step_user({"host": "wiim.local", "verify_ssl": True})
    assert result["type"] == "create_entry"
    flow.async_set_unique_id.assert_awaited_once_with("abc")
    flow._abort_if_unique_id_configured.assert_called_once_with(
        updates={"host": "wiim.local", "verify_ssl": True}
    )


async def test_config_flow_errors():
    from unittest.mock import patch

    from custom_components.wiim_local.config_flow import WiiMConfigFlow

    flow = WiiMConfigFlow()
    flow.hass = MagicMock()
    flow.async_show_form = MagicMock(return_value={})
    await flow.async_step_user({"host": "http://bad", "verify_ssl": True})
    assert flow.async_show_form.call_args.kwargs["errors"] == {"host": "invalid_host"}
    client = MagicMock()
    client.info = AsyncMock(side_effect=WiiMError("offline"))
    with (
        patch(
            "custom_components.wiim_local.config_flow.WiiMClient", return_value=client
        ),
        patch("custom_components.wiim_local.config_flow.async_get_clientsession"),
    ):
        await flow.async_step_user({"host": "wiim.local", "verify_ssl": True})
    assert flow.async_show_form.call_args.kwargs["errors"] == {"base": "cannot_connect"}


async def test_entry_setup_and_unload():
    from unittest.mock import patch

    from custom_components.wiim_local import async_setup_entry, async_unload_entry

    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    entry = MagicMock()
    entry.data = {"host": "wiim.local", "verify_ssl": True}
    co = MagicMock()
    co.async_config_entry_first_refresh = AsyncMock()
    with (
        patch("custom_components.wiim_local.async_get_clientsession"),
        patch("custom_components.wiim_local.WiiMCoordinator", return_value=co),
    ):
        assert await async_setup_entry(hass, entry)
    assert entry.runtime_data is co
    co.async_config_entry_first_refresh.assert_awaited_once()
    assert await async_unload_entry(hass, entry)


async def test_invalid_status_and_rejected_write():
    async with aiohttp.ClientSession() as session:
        with aioresponses() as mock:
            mock.get(BASE + "?command=getPlayerStatus", payload={"status": "OK"})
            mock.get(BASE + "?command=setPlayerCmd:pause", body="FAIL")
            client = WiiMClient(session, "192.168.1.5")
            with pytest.raises(WiiMError):
                await client.player()
            with pytest.raises(WiiMError):
                await client.request("setPlayerCmd:pause")
