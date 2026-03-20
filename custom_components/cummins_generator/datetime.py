"""Cummins Generator datetime platform."""
import re
import aiohttp
import logging
from datetime import datetime
from homeassistant.components.datetime import DateTimeEntity
from homeassistant.const import CONF_HOST
from homeassistant.helpers.entity import DeviceInfo

_LOGGER = logging.getLogger(__name__)
DOMAIN = "cummins_generator"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Cummins Generator datetime entity."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([CumminsGeneratorDateTime(coordinator)])


class CumminsGeneratorDateTime(DateTimeEntity):
    """DateTime entity for Cummins Generator time/date."""

    def __init__(self, coordinator):
        """Initialize the datetime entity."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.host}_datetime"
        self._attr_has_date = True
        self._attr_has_time = True
        self._value = None

    @property
    def name(self):
        return "Cummins Generator Date Time"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            name="Cummins Generator",
            manufacturer="Cummins",
            model="Generator",
        )

    @property
    def native_value(self):
        return self._value

    async def async_update(self):
        """Fetch current date/time from generator."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Basic {self.coordinator.auth}"}
                async with session.get(
                    f"http://{self.coordinator.host}/timedate.html", headers=headers
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        self._value = self._parse_datetime(html)
        except Exception as err:
            _LOGGER.error("Error fetching generator time: %s", err)

    def _parse_datetime(self, html):
        """Parse date/time from timedate.html."""
        # Month: writeMonths(3)
        month = re.search(r"writeMonths\((\d+)\)", html)
        # Day: writeOptions(1,31,20, FALSE)
        day = re.search(r"writeOptions\(1,31,(\d+)", html)
        # Year: writeOptions(2006,2031,2026, FALSE)
        year = re.search(r"writeOptions\(2006,2031,(\d+)", html)
        # Hour: value='8' on the hidden hours24 input
        hour = re.search(r"""name="@402"\s+value='(\d+)'""", html)
        # Minute: writeOptions(0,59,19, TRUE)
        minute = re.search(r"writeOptions\(0,59,(\d+)", html)

        if all([month, day, year, hour, minute]):
            return datetime(
                int(year.group(1)),
                int(month.group(1)),
                int(day.group(1)),
                int(hour.group(1)),
                int(minute.group(1)),
            )
        return None

    async def async_set_value(self, value: datetime) -> None:
        """Set the generator date/time."""
        params = (
            f"@448={value.month}&@449={value.day}&@450={value.year}"
            f"&@402={value.hour}&@403={value.minute}"
        )
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Basic {self.coordinator.auth}"}
                url = f"http://{self.coordinator.host}/wr_logical.cgi?{params}"
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        _LOGGER.error("Failed to set date/time: %s", response.status)
                    else:
                        self._value = value.replace(second=0, microsecond=0)
                        self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Error setting date/time: %s", err)
