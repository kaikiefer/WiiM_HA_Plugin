# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Kai Kiefer

"""Configure a WiiM by its local IP address."""

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WiiMClient, WiiMError, identity, validate_host
from .const import CONF_VERIFY_SSL, DOMAIN


class WiiMConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                host = validate_host(user_input[CONF_HOST])
                client = WiiMClient(
                    async_get_clientsession(self.hass),
                    host,
                    user_input[CONF_VERIFY_SSL],
                )
                info = await client.info()
                await client.player()
            except ValueError:
                errors[CONF_HOST] = "invalid_host"
            except WiiMError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(identity(info))
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_HOST: host,
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                    }
                )
                return self.async_create_entry(
                    title=info.get("DeviceName") or info.get("ssid") or "WiiM",
                    data={**user_input, CONF_HOST: host},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            errors=errors,
        )
