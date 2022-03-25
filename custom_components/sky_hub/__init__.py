"""The sky_hub component."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant

from .const import DATA_SKYQHUB, DOMAIN
from .router import SkyQHubRouter

PLATFORMS = [Platform.DEVICE_TRACKER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    router = SkyQHubRouter(hass, config_entry)
    await router.async_setup()

    router.async_on_close(config_entry.add_update_listener(update_listener))

    async def async_close_connection(event):  # pylint: disable=unused-argument
        """Close Sky Q Hub connection on HA Stop."""
        await router.close()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {DATA_SKYQHUB: router}

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    await hass.async_add_executor_job(register_router_services, hass, router)

    return True


async def async_unload_entry(hass, config):
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(config, PLATFORMS):
        router = hass.data[DOMAIN][config.entry_id][DATA_SKYQHUB]
        await router.close()
        hass.data[DOMAIN].pop(config.entry_id)

    return unload_ok


async def update_listener(hass, config_entry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


def register_router_services(hass, router):
    """Register the router services."""
    hass.services.register(DOMAIN, "delete_device", router.delete_device)
    hass.services.register(DOMAIN, "keep_device", router.keep_device)
    hass.services.register(DOMAIN, "unkeep_device", router.unkeep_device)
