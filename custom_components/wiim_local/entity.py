"""Shared device identity and action errors."""

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import WiiMError, identity
from .const import DOMAIN


class WiiMEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, suffix):
        super().__init__(coordinator)
        info = coordinator.info
        uid = identity(info)
        self._attr_unique_id = f"{uid}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, uid)},
            manufacturer="WiiM",
            name=info.get("DeviceName") or info.get("ssid") or "WiiM",
            model=info.get("project"),
            sw_version=info.get("firmware"),
        )

    async def command(self, command):
        try:
            await self.coordinator.client.request(command)
        except WiiMError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()
