"""Represent the Sky Q Hub router."""
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.components.device_tracker.const import DOMAIN as TRACKER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util
from pyskyqhub.skyq_hub import SkyQHub

from .const import (
    CAPABILITY_KEEP,
    CONF_TRACK_UNKNOWN,
    CONST_UNKNOWN,
    DEFAULT_TRACK_UNKNOWN,
    DOMAIN,
)

SCAN_INTERVAL = timedelta(seconds=20)

_LOGGER = logging.getLogger(__name__)


class SkyQHubRouter:
    """Representation of a Sky Q Hub router."""

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Initialize a Sky Q Hub router."""
        self.hass = hass
        self._config = config
        self._devices: dict[str, Any] = {}
        self._connected_devices = 0
        self._connect_error = False
        self._on_close: list[Callable] = []
        self._host = config.data.get(CONF_HOST, "192.168.1.254")
        self._websession = async_get_clientsession(hass)
        self._router = None
        self._options = {}
        self._options.update(config.options)

    async def async_setup(self) -> None:
        """Set up a Sky Q Hub router."""
        self._router = SkyQHub(self._websession, self._host)

        _LOGGER.debug("Initialising Sky Q Hub")
        await self._router.async_connect()
        if not self._router.success_init:
            raise ConfigEntryNotReady

        # Load tracked entities from registry
        track_entries = get_tracked_entities(self.hass, self._config)[0]

        for entry in track_entries:

            if entry.domain != TRACKER_DOMAIN:
                continue
            device_mac = format_mac(entry.unique_id)
            self._devices[device_mac] = SkyQHubDevInfo(device_mac, entry.original_name)

        # Update devices
        await self.async_update_devices()

        self.async_on_close(
            async_track_time_interval(self.hass, self.async_update_all, SCAN_INTERVAL)
        )

    async def async_close(self) -> None:
        """Close the connection."""
        _LOGGER.debug("async_close - needed")
        for func in self._on_close:
            func()
        self._on_close.clear()

    @callback
    def async_on_close(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when router is closed."""
        self._on_close.append(func)

    async def async_update_all(
        self, scaninterval=None  # pylint: disable=unused-argument
    ) -> None:
        """Update all Sky Q Hub platforms."""
        await self.async_update_devices()

    async def async_update_devices(self) -> None:
        """Update Sky Q Hub devices tracker."""
        new_device = False
        _LOGGER.debug("Checking devices for Sky Q router %s", self._host)

        if not (devices := await self._router.async_get_skyhub_data()):
            return

        # devices = TEST_DEVICES
        self._connected_devices = len(devices)
        consider_home = self._options.get(
            CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
        )
        track_unknown = self._options.get(CONF_TRACK_UNKNOWN, DEFAULT_TRACK_UNKNOWN)

        hub_devices = {
            format_mac(device.mac): {"device_info": device} for device in devices
        }

        for device_mac, device in self._devices.items():
            dev_info = hub_devices.pop(device_mac, None)
            device.update(dev_info, consider_home)

        for device_mac, dev_info in hub_devices.items():
            if not track_unknown and dev_info["device_info"].name == "UNKNOWN":
                continue
            new_device = True
            device = SkyQHubDevInfo(device_mac)
            device.update(dev_info)
            self._devices[device_mac] = device

        async_dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, "SkyQHub")},
            name=self._host,
            model="n/a",
            manufacturer="Sky",
            sw_version="n/a",
            configuration_url=f"http://{self._host}",
        )

    def delete_device(self, call):
        """Delete a device."""
        track_entries, entity_reg = get_tracked_entities(self.hass, self._config)
        for entity_id in call.data["entity_id"]:
            for entry in track_entries:
                if entry.entity_id == entity_id:
                    mac = format_mac(entry.unique_id)
                    self._devices.pop(mac)
                    async_dispatcher_send(self.hass, self.signal_device_delete, mac)
                    break
            entity_reg.async_remove(entity_id)

    def keep_device(self, call):
        """Keep a device."""
        self._change_keep(call, True)

    def unkeep_device(self, call):
        """Unkeep a device."""
        self._change_keep(call, False)

    def _change_keep(self, call, keep):
        entity_reg = er.async_get(self.hass)
        for entity_id in call.data["entity_id"]:
            entity_reg.async_update_entity(
                entity_id, capabilities={CAPABILITY_KEEP: keep}
            )
            signal = signal_device_keep(entity_id)
            async_dispatcher_send(self.hass, signal, keep)

    @property
    def signal_device_new(self) -> str:
        """Event specific per Sky Q Hub entry to signal new device."""
        return f"{DOMAIN}-device-new"

    @property
    def signal_device_update(self) -> str:
        """Event specific per Sky Q Hub entry to signal device update."""
        return f"{DOMAIN}-device-update"

    @property
    def signal_device_delete(self) -> str:
        """Event specific per Sky Q Hub entry to signal device deletes."""
        return f"{DOMAIN}-device-delete"

    @property
    def host(self) -> str:
        """Return router hostname."""
        return self._host

    @property
    def devices(self) -> dict[str, Any]:
        """Return devices."""
        return self._devices


class SkyQHubDevInfo:
    """Representation of a Sky Q Hub device info."""

    def __init__(self, mac, name=None):
        """Initialize a Sky Q Hub device info."""
        self._mac = mac
        self._name = name
        self._last_activity = None
        self._connected = False
        self._connection = None

    def update(self, dev_info=None, consider_home=0):
        """Update Sky Q Hub device info."""
        utc_point_in_time = dt_util.utcnow()
        if dev_info:
            devinfo = dev_info["device_info"]
            self._last_activity = utc_point_in_time
            self._connected = True
            self._connection = devinfo.connection
            if self._name != devinfo.name and devinfo.name.lower() != CONST_UNKNOWN:
                self._name = devinfo.name

        elif self._connected:
            self._connected = (
                utc_point_in_time - self._last_activity
            ).total_seconds() < consider_home

    @property
    def is_connected(self):
        """Return connected status."""
        return self._connected

    @property
    def mac(self):
        """Return device mac address."""
        return self._mac

    @property
    def name(self):
        """Return device name."""
        return self._name

    @property
    def connection(self):
        """Return device connection."""
        return self._connection

    @property
    def last_activity(self):
        """Return device last activity."""
        return self._last_activity


def get_tracked_entities(hass, config):
    """Get the tracked entities for this config."""
    entity_reg = er.async_get(hass)
    return er.async_entries_for_config_entry(entity_reg, config.entry_id), entity_reg


def signal_device_keep(entity_id) -> str:
    """Event specific per Sky Q Hub entry to signal device keep."""
    return f"{DOMAIN}-{entity_id}-device-keep"
