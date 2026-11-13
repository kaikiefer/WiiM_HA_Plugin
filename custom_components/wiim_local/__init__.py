# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Kai Kiefer

"""Local WiiM integration."""

from homeassistant.const import CONF_HOST, Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WiiMClient
from .const import CONF_VERIFY_SSL
from .coordinator import WiiMCoordinator

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.BUTTON]


async def async_setup_entry(hass, entry):
    client = WiiMClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data.get(CONF_VERIFY_SSL, True),
    )
    coordinator = WiiMCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
