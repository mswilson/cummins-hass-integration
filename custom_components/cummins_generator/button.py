"""Cummins Generator button platform."""
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)
DOMAIN = "cummins_generator"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Cummins Generator buttons."""
    client = hass.data[DOMAIN][config_entry.entry_id]["client"]

    buttons = [
        CumminsGeneratorButton(client, "start", "Start Genset", "@242=2"),
        CumminsGeneratorButton(client, "stop", "Stop Genset", "@242=1"),
        CumminsGeneratorButton(client, "enable_standby", "Enable Standby", "@385=1"),
        CumminsGeneratorButton(client, "disable_standby", "Disable Standby", "@385=0"),
        CumminsGeneratorButton(client, "exercise_now", "Exercise Now", "@242=3"),
        CumminsGeneratorSyncTimeButton(client),
    ]
    async_add_entities(buttons)


class CumminsGeneratorButton(ButtonEntity):
    """Representation of a Cummins Generator button."""

    def __init__(self, client, button_type, name, parameter):
        """Initialize the button."""
        self.client = client
        self.button_type = button_type
        self._name = name
        self.parameter = parameter
        self._attr_unique_id = f"{client.host}_{button_type}"

    @property
    def name(self):
        """Return the name of the button."""
        return f"Cummins Generator {self._name}"

    @property
    def device_info(self):
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.client.host)},
            name="Cummins Generator",
            manufacturer="Cummins",
            model="Generator",
        )

    async def async_press(self):
        """Handle the button press."""
        try:
            await self.client.get(f"/wr_logical.cgi?{self.parameter}")
        except Exception as err:
            _LOGGER.error("Error executing %s: %s", self._name, err)


class CumminsGeneratorSyncTimeButton(ButtonEntity):
    """Button to sync generator time to HA clock."""

    def __init__(self, client):
        self.client = client
        self._attr_unique_id = f"{client.host}_sync_time"

    @property
    def name(self):
        return "Cummins Generator Sync Time"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self.client.host)},
            name="Cummins Generator",
            manufacturer="Cummins",
            model="Generator",
        )

    async def async_press(self):
        now = dt_util.now()
        params = f"@448={now.month}&@449={now.day}&@450={now.year}&@402={now.hour}&@403={now.minute}"
        try:
            await self.client.get(f"/wr_logical.cgi?{params}")
        except Exception as err:
            _LOGGER.error("Error syncing time: %s", err)
