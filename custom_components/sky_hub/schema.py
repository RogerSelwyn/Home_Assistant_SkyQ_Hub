"""Schema for Sky Q Hub Integration."""

import voluptuous as vol
from homeassistant.const import CONF_HOST

DATA_SCHEMA = {vol.Required(CONF_HOST): str}
