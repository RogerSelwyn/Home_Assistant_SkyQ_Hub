[![Validate with hassfest](https://github.com/RogerSelwyn/Home_Assistant_SkyQ_Hub/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/RogerSelwyn/Home_Assistant_SkyQ_Hub/actions/workflows/hassfest.yaml) [![HACS Validate](https://github.com/RogerSelwyn/Home_Assistant_SkyQ_Hub/actions/workflows/hacs.yaml/badge.svg)](https://github.com/RogerSelwyn/Home_Assistant_SkyQ_Hub/actions/workflows/hacs.yaml) [![CodeFactor](https://www.codefactor.io/repository/github/rogerselwyn/Home_Assistant_SkyQ_Hub/badge)](https://www.codefactor.io/repository/github/rogerselwyn/home_assistant_skyq_hub) [![Downloads for latest release](https://img.shields.io/github/downloads/RogerSelwyn/Home_Assistant_SkyQ_Hub/latest/total.svg)](https://github.com/RogerSelwyn/Home_Assistant_SkyQ_Hub/releases/latest)

![GitHub release](https://img.shields.io/github/v/release/RogerSelwyn/Home_Assistant_SkyQ_Hub) [![maintained](https://img.shields.io/maintenance/yes/2025.svg)](#) [![maintainer](https://img.shields.io/badge/maintainer-%20%40RogerSelwyn-blue.svg)](https://github.com/RogerSelwyn) [![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration) 


# Sky Q Hub component for Home Assistant

This component is a significant re-write of the core 'sky_hub' integration. It is only supported via the UI, and there is no migration from the core version.

The components provides two configuration options.

* Track unknown - When enabled, devices with an unknown name are enabled for tracking in HASS.
* Track new - When enabled, newly discovered devices are enabled for tracking in HASS.

The component provides two types of entities:
* Device_Tracker - One for each device connected to the router inline with the configuration options above. The name and entity_id will be 'Unknown' where the device name is reported as unknown by the Sky Q Hub. However the Sky Q hub can be inconsistent, so the name and entity_id will change to a known name if it is reported by the Sky Q Hub. The name will continue to change with that reported by the Hub, the entity_id will only change once. The name will not change back to 'Unknown'.
* Sensor - Giving the SSID of the Wifi enabled on the router.

The following services are provided:
* sky_hub.delete_device - Deletes a device
* sky_hub.keep_device - Marks a device to be kept (this has no particular function other than adding a marker in the entity registry which can be used externally)
* sky_hub.unkeep_device - Unmarks a device to be kept 
