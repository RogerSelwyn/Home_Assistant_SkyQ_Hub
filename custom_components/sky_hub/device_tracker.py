"""Support for Sky Hub."""
from __future__ import annotations

import logging

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_TRACK_NEW,
    DATA_SKYQHUB,
    DEFAULT_DEVICE_NAME,
    DEFAULT_TRACK_NEW,
    DOMAIN,
    STATE_CABLED,
    STATE_DISCONNECTED,
)
from .router import SkyQHubRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for Sky Q Hub component."""
    router = hass.data[DOMAIN][config.entry_id][DATA_SKYQHUB]
    track_new = DEFAULT_TRACK_NEW
    if CONF_TRACK_NEW in config.options:
        track_new = config.options[CONF_TRACK_NEW]
    tracked: set = set()

    @callback
    def update_router():
        """Update the values of the router."""
        add_entities(router, async_add_entities, tracked, track_new)

    @callback
    def delete_device(mac):
        """Delete devices from tracking on the router."""
        tracked.remove(mac)
        # delete_entities(router, tracked, mac)

    router.async_on_close(
        async_dispatcher_connect(hass, router.signal_device_new, update_router)
    )
    router.async_on_close(
        async_dispatcher_connect(hass, router.signal_device_delete, delete_device)
    )

    update_router()


@callback
def add_entities(router, async_add_entities, tracked, track_new):
    """Add new tracker entities from the router."""
    new_tracked = []

    for mac, device in router.devices.items():
        if mac in tracked:
            continue

        new_tracked.append(SkyHubDevice(router, device, track_new))
        tracked.add(mac)

    if new_tracked:
        async_add_entities(new_tracked)


class SkyHubDevice(ScannerEntity):  # pylint: disable=abstract-method
    """This class queries a Sky Hub router."""

    _attr_should_poll = False

    def __init__(
        self,
        router: SkyQHubRouter,
        device,
        enabled_default,
    ):
        """Initialise the scanner."""
        self._router = router
        self._device = device
        self._attr_unique_id = device.mac
        self._attr_name = device.name or DEFAULT_DEVICE_NAME
        self._enabled_default = enabled_default
        if device.connection:
            self._connection = device.connection.lower().capitalize()
        else:
            self._connection = STATE_DISCONNECTED

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        return self._device.is_connected

    @property
    def source_type(self) -> str:
        """Return the source type."""
        return SOURCE_TYPE_ROUTER

    @property
    def hostname(self) -> str:
        """Return the hostname of device."""
        return self._device.name

    @property
    def icon(self) -> str:
        """Return device icon."""
        if self._device.is_connected:
            return "mdi:wifi" if self._connection != STATE_CABLED else "mdi:lan-connect"
        elif self._connection == STATE_DISCONNECTED:
            return "mdi:lan-disconnect"

        return (
            "mdi:wifi-off" if self._connection != STATE_CABLED else "mdi:lan-disconnect"
        )

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._device.mac

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        extra_attributes = {"connection": self._connection}
        if self._device.last_activity:
            extra_attributes[
                "last_time_reachable"
            ] = self._device.last_activity.isoformat(timespec="seconds")

        return extra_attributes

    @callback
    def async_on_demand_update(self):
        """Update state."""
        self._device = self._router.devices[self._device.mac]
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_device_update,
                self.async_on_demand_update,
            )
        )
