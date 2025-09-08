"""Cummins Generator button platform."""
import aiohttp
import base64
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_HOST
from homeassistant.helpers.entity import DeviceInfo

_LOGGER = logging.getLogger(__name__)
DOMAIN = "cummins_generator"

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Cummins Generator buttons."""
    host = config_entry.data[CONF_HOST]
    password = config_entry.data.get("password", "cummins")
    auth = base64.b64encode(f"admin:{password}".encode()).decode("ascii")
    
    buttons = [
        CumminsGeneratorButton(host, auth, "start", "Start Genset", "@242=2"),
        CumminsGeneratorButton(host, auth, "stop", "Stop Genset", "@242=1"),
        CumminsGeneratorButton(host, auth, "enable_standby", "Enable Standby", "@385=1"),
        CumminsGeneratorButton(host, auth, "disable_standby", "Disable Standby", "@385=0"),
        CumminsGeneratorButton(host, auth, "exercise_now", "Exercise Now", "@242=3"),
    ]
    async_add_entities(buttons)

class CumminsGeneratorButton(ButtonEntity):
    """Representation of a Cummins Generator button."""

    def __init__(self, host, auth, button_type, name, parameter):
        """Initialize the button."""
        self.host = host
        self.auth = auth
        self.button_type = button_type
        self._name = name
        self.parameter = parameter
        self._attr_unique_id = f"{host}_{button_type}"

    @property
    def name(self):
        """Return the name of the button."""
        return f"Cummins Generator {self._name}"

    @property
    def device_info(self):
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.host)},
            name="Cummins Generator",
            manufacturer="Cummins",
            model="Generator",
        )

    async def async_press(self):
        """Handle the button press."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Basic {self.auth}"}
                url = f"http://{self.host}/wr_logical.cgi?{self.parameter}"
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        _LOGGER.error(f"Failed to execute {self._name}: {response.status}")
        except Exception as err:
            _LOGGER.error(f"Error executing {self._name}: {err}")
