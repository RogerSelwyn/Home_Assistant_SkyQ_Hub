"""Configuration flow for the skyq platform."""

import ipaddress
import re

import voluptuous as vol
from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pyskyqhub.skyq_hub import SkyQHub

from .const import (
    CONF_TRACK_NEW,
    CONF_TRACK_UNKNOWN,
    DEFAULT_TRACK_NEW,
    DEFAULT_TRACK_UNKNOWN,
    DOMAIN,
)
from .schema import DATA_SCHEMA


class SkyHubConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initiliase the configuration flow."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input:
            if host_valid(user_input[CONF_HOST]):
                host = user_input[CONF_HOST]

                try:
                    await self._async_setuniqueid(host)
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title=host, data=user_input)

            errors[CONF_HOST] = "invalid_host"

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(DATA_SCHEMA), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def _async_setuniqueid(self, host):
        websession = async_get_clientsession(self.hass)
        hub = SkyQHub(websession, host)
        await hub.async_connect()
        if not hub.success_init:
            raise CannotConnect()
        await self.async_set_unique_id(f"skyqhub_{host.replace('.','')}")
        self._abort_if_unique_id_configured()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Sky Q Hub."""

    def __init__(self, config: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config = config
        self._name = config.title

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_TRACK_UNKNOWN,
                    default=self.config.options.get(
                        CONF_TRACK_UNKNOWN, DEFAULT_TRACK_UNKNOWN
                    ),
                ): bool,
                vol.Optional(
                    CONF_TRACK_NEW,
                    default=self.config.options.get(CONF_TRACK_NEW, DEFAULT_TRACK_NEW),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init",
            description_placeholders={CONF_NAME: self._name},
            data_schema=data_schema,
        )


def host_valid(host):
    """Return True if hostname or IP address is valid."""
    try:
        if ipaddress.ip_address(host).version == (4 or 6):
            return True
    except ValueError:
        disallowed = re.compile(r"[^a-zA-Z\d\-]")
        return all(x and not disallowed.search(x) for x in host.split("."))


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""
