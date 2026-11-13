# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Kai Kiefer

"""Coordinate device polling and serialize device requests."""

import logging
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WiiMError


class WiiMCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, client):
        super().__init__(
            hass,
            logging.getLogger(__name__),
            config_entry=entry,
            name="WiiM Local",
            update_interval=timedelta(seconds=5),
        )
        self.client = client
        self.info = {}
        self.updated_at = None

    async def _async_update_data(self):
        from homeassistant.util.dt import utcnow

        try:
            if not self.info:
                self.info = await self.client.info()
            player = await self.client.player()
        except WiiMError as err:
            raise UpdateFailed(str(err)) from err
        metadata = {}
        try:
            response = await self.client.request("getMetaInfo", object_response=True)
            raw = response.get("metaData", {})
            if isinstance(raw, dict):
                metadata = {str(k).strip(): v for k, v in raw.items()}
        except WiiMError:
            pass  # Optional on older firmware; never retain stale track information.
        self.updated_at = utcnow()
        return {"player": player, "metadata": metadata}
