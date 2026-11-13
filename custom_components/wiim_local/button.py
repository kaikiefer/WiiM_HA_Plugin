# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Kai Kiefer

"""WiiM Home preset shortcuts."""

from homeassistant.components.button import ButtonEntity

from .entity import WiiMEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([WiiMPreset(entry.runtime_data, n) for n in range(1, 13)])


class WiiMPreset(WiiMEntity, ButtonEntity):
    _attr_icon = "mdi:playlist-play"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, number):
        super().__init__(coordinator, f"preset_{number}")
        self.number = number
        self._attr_name = f"Preset {number}"

    async def async_press(self):
        await self.command(f"MCUKeyShortClick:{self.number}")
