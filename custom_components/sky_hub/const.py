"""Sky_hub component constants."""
from dataclasses import dataclass, field

CAPABILITY_KEEP = "keep"
CONF_TRACK_NEW = "track_new"
CONF_TRACK_UNKNOWN = "track_unknown"
CONST_UNKNOWN = "unknown"
DATA_SKYQHUB = "skyqhub"
DEFAULT_DEVICE_NAME = "Unknown device"
DEFAULT_KEEP = False
DEFAULT_TRACK_NEW = False
DEFAULT_TRACK_UNKNOWN = False
DOMAIN = "sky_hub"
STATE_DISCONNECTED = "Disconnected"
STATE_CABLED = "Cabled"


@dataclass
class _Device:
    mac: str = field(init=True, repr=True, compare=True)
    name: str = field(init=True, repr=True, compare=True)
    connection: str = field(init=True, repr=True, compare=True)

    def asdict(self):
        """Convert to dictionary."""
        return {"mac": self.mac}


TEST_DEVICES = [
    _Device(mac="70:4f:57:99:a3:f0", name="UNKNOWN", connection="Cabled"),
    _Device(mac="68:ff:7b:cc:a9:5c", name="UNKNOWN", connection="Cabled"),
    _Device(mac="e4:95:6e:44:cd:7d", name="GL-AR750S-b60", connection="Cabled"),
    _Device(mac="48:ee:0c:82:94:bc", name="UNKNOWN", connection="Cabled"),
    _Device(mac="20:47:ed:c5:9a:72", name="SKY+HD", connection="UnKnown"),
    _Device(mac="cc:a7:c1:5b:75:2e", name="UNKNOWN", connection="Cabled"),
    _Device(mac="8c:49:62:67:9e:14", name="RokuStreamingStick", connection="UnKnown"),
    _Device(mac="18:b4:30:bf:4d:e6", name="09AA01AC101702WV", connection="Wireless"),
    _Device(
        mac="68:14:01:64:2e:03", name="android-729ca2c12c9d1b02", connection="Wireless"
    ),
]
TEST_DEVICES = [
    # _Device(mac="70:4f:57:99:a3:f0", name="UNKNOWN", connection="Cabled"),
    _Device(mac="68:ff:7b:cc:a9:5c", name="UNKNOWN", connection="Cabled"),
    _Device(mac="e4:95:6e:44:cd:7d", name="GL-AR750S-b60", connection="Cabled"),
    _Device(mac="48:ee:0c:82:94:bc", name="UNKNOWN", connection="Cabled"),
    _Device(mac="20:47:ed:c5:9a:72", name="SKY+HD", connection="UnKnown"),
    _Device(mac="cc:a7:c1:5b:75:2e", name="UNKNOWN", connection="Cabled"),
    _Device(mac="8c:49:62:67:9e:14", name="RokuStreamingStick", connection="UnKnown"),
    _Device(mac="18:b4:30:bf:4d:e6", name="09AA01AC101702WV", connection="Wireless"),
    _Device(
        mac="68:14:01:64:2e:03", name="android-729ca2c12c9d1b02", connection="Wireless"
    ),
]
