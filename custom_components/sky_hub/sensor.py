"""Sky Q Hub status sensors."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (ATTRIBUTE_AVAILABLE, ATTRIBUTE_SSID, ATTRIBUTE_WAN_MAC,
                    CONST_SENSOR_NAME, DATA_SKYQHUB, DOMAIN)
from .router import SkyQHubRouter


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    router: SkyQHubRouter = hass.data[DOMAIN][entry.entry_id][DATA_SKYQHUB]

    skyqwifi = SkyQConfigSensor(router)

    @callback
    async def async_update_sensor():
        """Update the values of the sensor."""
        await skyqwifi.async_on_demand_update()

    await router.async_on_close(
        async_dispatcher_connect(hass, router.signal_sensor_update, async_update_sensor)
    )

    async_add_entities([skyqwifi])


class SkyQConfigSensor(SensorEntity):
    """Config Sensor Entity for SkyQ Hub Device."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, router: SkyQHubRouter):
        """Initialize the Config sensor."""
        self._router = router

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._router.wan_ip

    @property
    def name(self):
        """Get the name of the devices."""
        return CONST_SENSOR_NAME

    @property
    def unique_id(self):
        """Get the unique id of the device."""
        return f"{DATA_SKYQHUB}_{self._router.wan_mac}"

    @property
    def device_info(self):
        """Entity device information."""
        return self._router.device_info

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return {
            ATTRIBUTE_AVAILABLE: self._router.available,
            ATTRIBUTE_SSID: self._router.ssid,
            ATTRIBUTE_WAN_MAC: self._router.wan_mac,
        }

    async def async_on_demand_update(self):
        """Update state."""
        self.async_write_ha_state()
