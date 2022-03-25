"""Diagnostics support for Sky Q Hub."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry  # pylint: disable=unused-argument
) -> dict:
    """Return diagnostics for a config entry."""
    return {
        "config_entry_data": dict(config_entry.data),
        "config_entry_options": dict(config_entry.options),
    }
