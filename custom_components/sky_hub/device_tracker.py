"""Support for Sky Hub."""
from __future__ import annotations

import logging

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CAPABILITY_KEEP,
    CONF_TRACK_NEW,
    DATA_SKYQHUB,
    DEFAULT_DEVICE_NAME,
    DEFAULT_KEEP,
    DEFAULT_TRACK_NEW,
    DOMAIN,
    STATE_CABLED,
    STATE_DISCONNECTED,
)
from .router import SkyQHubRouter, get_tracked_entities, signal_device_keep

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
        add_entities(hass, config, router, async_add_entities, tracked, track_new)

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
def add_entities(hass, config, router, async_add_entities, tracked, track_new):
    """Add new tracker entities from the router."""
    new_tracked = []

    tracked_entities = get_tracked_entities(hass, config)[0]
    for mac, device in router.devices.items():
        if mac in tracked:
            continue

        keep = DEFAULT_KEEP
        for tracked_entity in tracked_entities:
            if (
                format_mac(tracked_entity.unique_id) == mac
                and tracked_entity.capabilities
            ):
                keep = tracked_entity.capabilities.get(CAPABILITY_KEEP, DEFAULT_KEEP)

        new_tracked.append(SkyHubDevice(router, device, track_new, keep))
        tracked.add(mac)

    if new_tracked:
        async_add_entities(new_tracked)


class SkyHubDevice(ScannerEntity):  # pylint: disable=abstract-method
    """This class queries a Sky Hub router."""

    _attr_should_poll = False

    def __init__(self, router: SkyQHubRouter, device, enabled_default, keep):
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
        self._keep = keep

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

        if self._connection == STATE_DISCONNECTED:
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

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        if self._keep and self._keep is True:
            return {CAPABILITY_KEEP: self._keep}

        return None

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
        signal = signal_device_keep(self.entity_id)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal,
                self.async_device_keep,
            )
        )

    @callback
    def async_device_keep(self, keep):
        """Update keep capability."""
        self._keep = keep
