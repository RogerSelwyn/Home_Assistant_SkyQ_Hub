"""Represent the Sky Q Hub router."""
import logging
from collections.abc import Callable
from copy import deepcopy
from datetime import timedelta
from typing import Any

from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.components.device_tracker.const import DOMAIN as TRACKER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
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
    CAPABILITY_CONNECTION,
    CAPABILITY_KEEP,
    CONF_TRACK_UNKNOWN,
    CONST_UNKNOWN,
    DEFAULT_KEEP,
    DEFAULT_TRACK_UNKNOWN,
    DOMAIN,
)

SCAN_INTERVAL = timedelta(seconds=20)

_LOGGER = logging.getLogger(__name__)


class SkyQHubRouter:
    """Representation of a Sky Q Hub router."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize a Sky Q Hub router."""
        self.hass = hass
        self._available = False
        self._ssid = None
        self._wan_mac = None
        self._wan_ip = None
        self._config_entry = config_entry
        self._devices: dict[str, Any] = {}
        # self._connected_devices = 0
        # self._connect_error = False
        self._on_close: list[Callable] = []
        self._host = config_entry.data.get(CONF_HOST, "192.168.1.254")
        self._websession = async_get_clientsession(hass)
        self._router = None
        self._options = {}
        self._options |= config_entry.options

    async def async_setup(self) -> None:
        """Set up a Sky Q Hub router."""
        self._router = SkyQHub(self._websession, self._host)

        _LOGGER.debug("Initialising Sky Q Hub")
        await self._router.async_connect()
        if not self._router.success_init:
            raise ConfigEntryNotReady

        # Load tracked entities from registry
        entity_reg = er.async_get(self.hass)
        track_entries = er.async_entries_for_config_entry(
            entity_reg, self._config_entry.entry_id
        )
        for entry in track_entries:

            if entry.domain != TRACKER_DOMAIN:
                continue
            device_mac = format_mac(entry.unique_id)
            self._devices[device_mac] = SkyQHubDevInfo(
                device_mac, entry.original_name, entry.capabilities
            )

        # Update devices
        await self._async_update_devices()

        await self.async_on_close(
            async_track_time_interval(self.hass, self.async_update_all, SCAN_INTERVAL)
        )

    async def async_close(self) -> None:
        """Close the connection."""
        for func in self._on_close:
            func()
        self._on_close.clear()

    @callback
    async def async_on_close(self, func: CALLBACK_TYPE) -> None:
        """Add a function to call when router is closed."""
        self._on_close.append(func)

    async def async_update_all(
        self, scaninterval=None  # pylint: disable=unused-argument
    ) -> None:
        """Update all Sky Q Hub platforms."""
        await self._async_update_devices()

    async def _async_update_devices(self) -> None:
        """Update Sky Q Hub devices tracker."""
        new_device = False
        _LOGGER.debug("Checking devices for Sky Q router %s", self._host)

        devices = await self._router.async_get_skyhub_data()
        if not devices:
            return
        await self._async_update_sensors()

        # self._connected_devices = len(devices)
        consider_home = self._options.get(
            CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME.total_seconds()
        )
        track_unknown = self._options.get(CONF_TRACK_UNKNOWN, DEFAULT_TRACK_UNKNOWN)

        hub_devices = {
            format_mac(device.mac): {"device_info": device} for device in devices
        }

        for device_mac, device in self._devices.items():
            dev_info = hub_devices.pop(device_mac, None)
            await device.async_update(dev_info, self.hass, consider_home=consider_home)

        for device_mac, dev_info in hub_devices.items():
            if (
                not track_unknown
                and dev_info["device_info"].name.lower() == CONST_UNKNOWN
            ):
                continue
            new_device = True
            device = SkyQHubDevInfo(device_mac)
            await device.async_update(dev_info, self.hass)
            self._devices[device_mac] = device

        async_dispatcher_send(self.hass, self.signal_device_update)
        if new_device:
            async_dispatcher_send(self.hass, self.signal_device_new)

    async def _async_update_sensors(self):
        self._wan_mac = self._router.wan_mac
        self._ssid = self._router.ssid
        update_sensor = False
        ipaddr = self._router.wan_ip
        if ipaddr != self._wan_ip:
            update_sensor = True
            self._wan_ip = ipaddr
        available = self._router.available
        if available != self._available:
            update_sensor = True
            self._available = available

        if update_sensor:
            async_dispatcher_send(self.hass, self.signal_sensor_update)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._router.wan_mac)},
            name=self._host,
            model="Sky Q Hub",
            manufacturer="Sky",
            sw_version="n/a",
            configuration_url=self._router.url,
        )

    @property
    def available(self):
        """Return whether router is responding correctly."""
        return self._available

    @property
    def ssid(self):
        """Return the ssid of wifi on router."""
        return self._ssid

    @property
    def wan_ip(self):
        """Return the wan ip address router."""
        return self._wan_ip

    @property
    def wan_mac(self):
        """Return the wan mac address router."""
        return self._wan_mac

    def delete_device(self, call):
        """Delete a device."""
        entity_reg = er.async_get(self.hass)
        for entity_id in call.data["entity_id"]:
            entity = entity_reg.async_get(entity_id)
            mac = format_mac(entity.unique_id)
            self._devices.pop(mac)
            async_dispatcher_send(self.hass, self.signal_device_delete, mac)
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
            entity = entity_reg.async_get(entity_id)
            capabilities = deepcopy(entity.capabilities)
            capabilities[CAPABILITY_KEEP] = keep
            entity_reg.async_update_entity(entity_id, capabilities=capabilities)
            device = self.devices[format_mac(entity.unique_id)]
            device.update_keep(keep)
            signal = signal_device_keep(entity_id)
            async_dispatcher_send(self.hass, signal)

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
    def signal_sensor_update(self) -> str:
        """Event specific per Sky Q Hub entry to update sensor."""
        return f"{DOMAIN}-sensor-update"

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

    def __init__(self, mac, name=None, capabilities=None):
        """Initialize a Sky Q Hub device info."""
        self._mac = mac
        self._name = name
        self._connection = None
        self._keep = False
        self._last_activity = None
        self._connected = False
        # self._start = 0

        if capabilities:
            self._connection = capabilities.get(CAPABILITY_CONNECTION)
            self._keep = capabilities.get(CAPABILITY_KEEP, DEFAULT_KEEP)

    async def async_update(self, dev_info, hass, consider_home=0):
        """Update Sky Q Hub device info."""
        utc_point_in_time = dt_util.utcnow()
        if not dev_info:
            if self._connected:
                self._connected = (
                    utc_point_in_time - self._last_activity
                ).total_seconds() < consider_home
            return

        devinfo = dev_info["device_info"]
        self._last_activity = utc_point_in_time
        self._connected = True
        await self._async_update_entity_name_id(hass, devinfo)
        await self._async_update_entity_connection(hass, devinfo)

    def update_keep(self, keep):
        """Update keep property provided via service."""
        self._keep = keep

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
    def last_activity(self):
        """Return device last activity."""
        return self._last_activity

    @property
    def connection(self) -> str:
        """Return connection."""
        return self._connection

    @property
    def keep(self) -> str:
        """Return connection."""
        return self._keep

    async def _async_update_entity_name_id(self, hass, devinfo):
        if (
            self._name
            and self._name != devinfo.name
            and self._name.lower() == CONST_UNKNOWN
        ):
            entity_reg = er.async_get(hass)
            new_entity_id = entity_reg.async_generate_entity_id(
                Platform.DEVICE_TRACKER, devinfo.name
            )
            old_entity_id = entity_reg.async_get_entity_id(
                Platform.DEVICE_TRACKER, DOMAIN, self._mac
            )
            entity_reg.async_update_entity(
                old_entity_id, new_entity_id=new_entity_id, name=devinfo.name
            )
            self._name = devinfo.name
        elif not self._name:
            self._name = devinfo.name

    async def _async_update_entity_connection(self, hass, devinfo):
        # self._start += 1
        # if self._start == 2:
        #     devinfo.connection = "blah"
        if (
            self._connection
            and self._connection != devinfo.connection
            and devinfo.connection.lower() != CONST_UNKNOWN
        ):
            entity_reg = er.async_get(hass)
            entity_id = entity_reg.async_get_entity_id(
                Platform.DEVICE_TRACKER, DOMAIN, self._mac
            )
            entity = entity_reg.async_get(entity_id)
            capabilities = deepcopy(entity.capabilities)
            capabilities[CAPABILITY_CONNECTION] = devinfo.connection
            entity_reg.async_update_entity(entity_id, capabilities=capabilities)
            self._connection = devinfo.connection
        elif not self._connection:
            self._connection = devinfo.connection


def signal_device_keep(entity_id) -> str:
    """Event specific per Sky Q Hub entry to signal device keep."""
    return f"{DOMAIN}-{entity_id}-device-keep"
