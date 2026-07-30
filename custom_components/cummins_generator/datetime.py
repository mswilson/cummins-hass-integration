"""Cummins Generator datetime platform."""
import re
import logging
from datetime import datetime, timedelta
from homeassistant.components.datetime import DateTimeEntity
from homeassistant.core import callback
from homeassistant.util import dt as dt_util
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(hours=1)
DOMAIN = "cummins_generator"


def signal_time_updated(host: str) -> str:
    """Dispatcher signal fired when a write pushes a fresh value."""
    return f"cummins_generator_datetime_updated_{host}"


def signal_time_read(host: str) -> str:
    """Dispatcher signal fired after each successful read from the generator.

    Payload is (generator_utc, ha_utc_at_read).
    """
    return f"cummins_generator_datetime_read_{host}"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Cummins Generator datetime entity."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [CumminsGeneratorDateTime(data["coordinator"], data["client"])],
        update_before_add=True,
    )


class CumminsGeneratorDateTime(DateTimeEntity):
    """DateTime entity for Cummins Generator time/date."""

    def __init__(self, coordinator, client):
        """Initialize the datetime entity."""
        self.coordinator = coordinator
        self.client = client
        self._attr_unique_id = f"{client.host}_datetime"
        self._attr_has_date = True
        self._attr_has_time = True
        self._value = None

    @property
    def name(self):
        return "Cummins Generator Date Time"

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self.client.host)},
            name="Cummins Generator",
            manufacturer="Cummins",
            model="Generator",
        )

    @property
    def native_value(self):
        return self._value

    async def async_added_to_hass(self) -> None:
        """Subscribe to write-side pushes from the sync button."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_time_updated(self.client.host),
                self._handle_pushed_value,
            )
        )

    @callback
    def _handle_pushed_value(self, value: datetime) -> None:
        """Adopt a value freshly written to the generator, no re-read needed."""
        self._value = value.replace(second=0, microsecond=0)
        self.async_write_ha_state()

    async def async_update(self):
        """Fetch current date/time from generator."""
        try:
            html = await self.client.get("/timedate.html")
        except Exception as err:
            _LOGGER.error("Error fetching generator time: %s", err)
            return
        parsed = self._parse_datetime(html)
        if parsed is None:
            return
        ha_now = dt_util.utcnow()
        self._value = parsed
        if self.hass is not None:
            async_dispatcher_send(
                self.hass, signal_time_read(self.client.host), parsed, ha_now
            )

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
            local = datetime(
                int(year.group(1)),
                int(month.group(1)),
                int(day.group(1)),
                int(hour.group(1)),
                int(minute.group(1)),
                tzinfo=dt_util.DEFAULT_TIME_ZONE,
            )
            return dt_util.as_utc(local)
        return None

    async def async_set_value(self, value: datetime) -> None:
        """Set the generator date/time."""
        local = dt_util.as_local(value)
        params = (
            f"@448={local.month}&@449={local.day}&@450={local.year}"
            f"&@402={local.hour}&@403={local.minute}"
        )
        try:
            await self.client.get(f"/wr_logical.cgi?{params}")
            self._handle_pushed_value(value)
        except Exception as err:
            _LOGGER.error("Error setting date/time: %s", err)
