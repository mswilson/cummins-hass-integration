"""Cummins Generator select platform."""
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)
DOMAIN = "cummins_generator"
# One endpoint per tick; three endpoints -> ~5 minute refresh per endpoint.
# Keeps total request rate to the generator well below what causes the
# InterNiche 2.0 stack to run out of packet buffers. See
# docs/generator-network-stack.md.
SCAN_INTERVAL = timedelta(seconds=100)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Cummins Generator select entities."""
    client = hass.data[DOMAIN][config_entry.entry_id]["client"]
    coordinator = CumminsLoadCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    
    selects = [
        CumminsGeneratorSelect(coordinator, "load_mode", "Load Mode", ["Manual", "Automatic"]),
        CumminsGeneratorSelect(coordinator, "load_1", "Load 1", ["Disconnected", "Connected"]),
        CumminsGeneratorSelect(coordinator, "load_2", "Load 2", ["Disconnected", "Connected"]),
        CumminsGeneratorSelect(coordinator, "exercise_frequency", "Exercise Frequency", ["Never", "Weekly", "Bimonthly", "Monthly"]),
        CumminsGeneratorSelect(coordinator, "exercise_day", "Exercise Day", ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]),
        CumminsGeneratorSelect(coordinator, "exercise_hour", "Exercise Hour", [str(i) for i in range(24)]),
        CumminsGeneratorSelect(coordinator, "exercise_minute", "Exercise Minute", ["00", "15", "30", "45"]),
    ]
    async_add_entities(selects)

class CumminsLoadCoordinator(DataUpdateCoordinator):
    """Data coordinator for Cummins Generator load management.

    Each tick fetches a single endpoint, cycling through the three
    endpoints below. On a `SCAN_INTERVAL` of 100 s, every endpoint sees
    a fresh read every 5 minutes. The last-known values for the other
    two endpoints are preserved so entities stay populated.
    """

    ENDPOINTS = ("loads_data", "loads", "exercise")

    def __init__(self, hass, client):
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name="Cummins Load", update_interval=SCAN_INTERVAL)
        self.client = client
        self.host = client.host
        self._index = 0
        self._data: dict = {}

    async def _async_update_data(self):
        """Fetch one endpoint's worth of load data."""
        endpoint = self.ENDPOINTS[self._index]
        self._index = (self._index + 1) % len(self.ENDPOINTS)
        try:
            fresh = await self._fetch_endpoint(endpoint)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with generator: {err}")
        self._data.update(fresh)
        return dict(self._data)

    async def refresh_endpoint(self, endpoint: str) -> None:
        """Fetch a single endpoint immediately, e.g. after a write.

        Bypasses the round-robin cycle and merges the result into the
        coordinator's data.
        """
        try:
            fresh = await self._fetch_endpoint(endpoint)
        except Exception as err:
            _LOGGER.warning("Refresh of %s failed: %s", endpoint, err)
            return
        self._data.update(fresh)
        self.async_set_updated_data(dict(self._data))

    async def _fetch_endpoint(self, endpoint: str) -> dict:
        """Fetch one endpoint and return its parsed key/value pairs."""
        if endpoint == "loads":
            html = await self.client.get("/loads.html")
            return self._parse_loads_html(html)
        if endpoint == "loads_data":
            body = await self.client.get("/loads_data.html")
            lines = body.strip().split('\n')
            if len(lines) < 3:
                return {}
            return {
                "load_1": "Connected" if int(lines[1]) == 0 else "Disconnected",
                "load_2": "Connected" if int(lines[2]) == 0 else "Disconnected",
            }
        if endpoint == "exercise":
            html = await self.client.get("/exercise.html")
            return self._parse_exercise_html(html)
        return {}

    def _parse_loads_html(self, html):
        """Parse load management mode from HTML."""
        import re
        
        # Look for writeSingleOption pattern to determine mode
        # Manual: writeSingleOption( 1, !(0 & 0x01), "Manual" );
        # Auto: writeSingleOption( 1, !(1 & 0x01), "Manual" );
        mode_match = re.search(r'writeSingleOption\(\s*1,\s*!\((\d+)\s*&\s*0x01\),\s*"Manual"\s*\)', html)
        mode_value = int(mode_match.group(1)) if mode_match else 0
        
        return {
            "load_mode": "Manual" if mode_value == 0 else "Automatic",
        }

    def _parse_exercise_html(self, html):
        """Parse exercise settings from HTML."""
        import re
        
        # Find frequency: var match = 3; (before writeSingleOption calls for frequency)
        freq_section = re.search(r'var match = (\d+);.*?writeSingleOption\(0,match == 0, "Never"\)', html, re.DOTALL)
        frequency = int(freq_section.group(1)) if freq_section else 0
        freq_options = ["Never", "Weekly", "Bimonthly", "Monthly"]
        
        # Find day: writeDays(6)
        day_match = re.search(r'writeDays\((\d+)\)', html)
        day = int(day_match.group(1)) if day_match else 0
        day_options = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        
        # Find hour: hrs24ToHrs12(10)
        hour_match = re.search(r'hrs24ToHrs12\((\d+)\)', html)
        hour = int(hour_match.group(1)) if hour_match else 0
        
        # Find minute: var match = 0; (before writeSingleOption calls for minutes)
        # Find all match variables and get the last one (for minutes)
        all_matches = re.findall(r'var match = (\d+);', html)
        minute = all_matches[-1] if all_matches else "0"
        min_options = ["00", "15", "30", "45"]
        
        return {
            "exercise_frequency": freq_options[frequency] if frequency < len(freq_options) else "Never",
            "exercise_day": day_options[day] if day < len(day_options) else "Sunday", 
            "exercise_hour": str(hour),
            "exercise_minute": minute if minute in min_options else "00",
        }

class CumminsGeneratorSelect(CoordinatorEntity, SelectEntity):
    """Representation of a Cummins Generator select entity."""

    def __init__(self, coordinator, select_type, name, options):
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.select_type = select_type
        self._name = name
        self._attr_options = options
        self._attr_unique_id = f"{coordinator.host}_{select_type}"

    @property
    def name(self):
        """Return the name of the select entity."""
        return f"Cummins Generator {self._name}"

    @property
    def device_info(self):
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.host)},
            name="Cummins Generator",
            manufacturer="Cummins",
            model="Generator",
        )

    @property
    def current_option(self):
        """Return the current option."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.select_type)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        refresh_endpoint = "loads"
        if self.select_type == "load_mode":
            value = "1" if option == "Manual" else "2"
            path = f"/wr_logical.cgi?@426={value}"
        elif self.select_type == "load_1":
            value = "3" if option == "Disconnected" else "4"
            path = f"/wr_logical.cgi?@426={value}"
            refresh_endpoint = "loads_data"
        elif self.select_type == "load_2":
            value = "5" if option == "Disconnected" else "6"
            path = f"/wr_logical.cgi?@426={value}"
            refresh_endpoint = "loads_data"
        elif self.select_type == "exercise_frequency":
            value = ["0", "1", "2", "3"][["Never", "Weekly", "Bimonthly", "Monthly"].index(option)]
            path = f"/wr_logical.cgi?@425={value}"
            refresh_endpoint = "exercise"
        elif self.select_type == "exercise_day":
            value = str(["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"].index(option))
            path = f"/wr_logical.cgi?@391={value}"
            refresh_endpoint = "exercise"
        elif self.select_type == "exercise_hour":
            path = f"/wr_logical.cgi?@392={option}"
            refresh_endpoint = "exercise"
        elif self.select_type == "exercise_minute":
            path = f"/wr_logical.cgi?@393={option}"
            refresh_endpoint = "exercise"
        else:
            return

        try:
            await self.coordinator.client.get(path)
            await self.coordinator.refresh_endpoint(refresh_endpoint)
        except Exception as err:
            _LOGGER.error("Error setting %s: %s", self._name, err)
