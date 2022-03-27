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
    CAPABILITY_CONNECTION,
    CAPABILITY_KEEP,
    CONF_TRACK_NEW,
    CONST_UNKNOWN,
    DATA_SKYQHUB,
    DEFAULT_DEVICE_NAME,
    DEFAULT_TRACK_NEW,
    DOMAIN,
    STATE_CABLED,
    STATE_WIRELESS,
)
from .router import SkyQHubRouter, signal_device_keep

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

    def __init__(self, router: SkyQHubRouter, device, enabled_default):
        """Initialise the scanner."""
        self._router = router
        self._device = device
        self._attr_unique_id = device.mac
        self._attr_name = device.name or DEFAULT_DEVICE_NAME
        self._enabled_default = enabled_default

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
            if self._device.connection == STATE_WIRELESS:
                return "mdi:wifi"
            elif self._device.connection == STATE_CABLED:
                return "mdi:lan-pending"
            else:
                return "mdi:lan-connect"

        return (
            "mdi:lan-disconnect"
            if self._device.connection != STATE_WIRELESS
            else "mdi:wifi-off"
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
    def capability_attributes(self):
        """Return capability attributes."""
        capabilities = {}
        if self._device.keep and self._device.keep is True:
            capabilities[CAPABILITY_KEEP] = self._device.keep

        if self._device.connection != CONST_UNKNOWN:
            capabilities[CAPABILITY_CONNECTION] = self._device.connection

        return capabilities

    @callback
    def async_on_demand_update(self):
        """Update state."""
        self._device = self._router.devices[self._device.mac]
        # if not self._attr_extra_state_attributes:
        self._attr_extra_state_attributes = {}
        if self._device.last_activity:
            self._attr_extra_state_attributes[
                "last_time_reachable"
            ] = self._device.last_activity.isoformat(timespec="seconds")

        if self._device.keep and self._device.keep is True:
            self._attr_extra_state_attributes[CAPABILITY_KEEP] = self._device.keep

        if self._device.connection != CONST_UNKNOWN:
            self._attr_extra_state_attributes[
                CAPABILITY_CONNECTION
            ] = self._device.connection

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
        signal = signal_device_keep(self.entity_id)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal,
                self.async_device_capability,
            )
        )

    @callback
    def async_device_capability(self):
        """Update capability."""
        self.async_on_demand_update()
