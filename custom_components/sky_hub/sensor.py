"""Sky Q Hub status sensors."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_SKYQHUB, DOMAIN
from .router import SkyQHubRouter


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    router: SkyQHubRouter = hass.data[DOMAIN][entry.entry_id][DATA_SKYQHUB]

    skyqwifi = SkyQWifiSensor(router)

    @callback
    async def async_update_sensor():
        """Update the values of the sensor."""
        await skyqwifi.async_on_demand_update()

    router.async_on_close(
        async_dispatcher_connect(hass, router.signal_sensor_update, async_update_sensor)
    )

    async_add_entities([skyqwifi])


class SkyQWifiSensor(SensorEntity):
    """Wifi Sensor Entity for SkyQ Device."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, router: SkyQHubRouter):
        """Initialize the Wifi sensor."""
        self._router = router

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._router.ssid

    @property
    def name(self):
        """Get the name of the devices."""
        return "Sky Q Hub SSID"

    @property
    def unique_id(self):
        """Get the unique id of the device."""
        return "skyqhub"

    @property
    def device_info(self):
        """Entity device information."""
        return self._router.device_info

    async def async_on_demand_update(self):
        """Update state."""
        self.async_write_ha_state()
