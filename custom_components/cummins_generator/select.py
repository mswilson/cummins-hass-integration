"""Cummins Generator select platform."""
import aiohttp
import base64
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_HOST
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)
DOMAIN = "cummins_generator"
SCAN_INTERVAL = timedelta(seconds=30)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Cummins Generator select entities."""
    host = config_entry.data[CONF_HOST]
    password = config_entry.data.get("password", "cummins")
    coordinator = CumminsLoadCoordinator(hass, host, password)
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
    """Data coordinator for Cummins Generator load management."""

    def __init__(self, hass, host, password):
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name="Cummins Load", update_interval=SCAN_INTERVAL)
        self.host = host
        self.auth = base64.b64encode(f"admin:{password}".encode()).decode("ascii")

    async def _async_update_data(self):
        """Fetch load data from the generator."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Basic {self.auth}"}
                
                # Get load data from loads.html
                load_data = {}
                async with session.get(f"http://{self.host}/loads.html", headers=headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        load_data = self._parse_loads_html(html)
                
                # Get load status from loads_data.html
                async with session.get(f"http://{self.host}/loads_data.html", headers=headers) as response:
                    if response.status == 200:
                        data = await response.text()
                        lines = data.strip().split('\n')
                        if len(lines) >= 3:
                            load_data.update({
                                "load_1": "Connected" if int(lines[1]) == 0 else "Disconnected",
                                "load_2": "Connected" if int(lines[2]) == 0 else "Disconnected",
                            })
                
                # Get exercise data
                exercise_data = {}
                async with session.get(f"http://{self.host}/exercise.html", headers=headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        exercise_data = self._parse_exercise_html(html)
                
                return {**load_data, **exercise_data}
                
        except Exception as err:
            raise UpdateFailed(f"Error communicating with generator: {err}")

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

class CumminsGeneratorSelect(SelectEntity):
    """Representation of a Cummins Generator select entity."""

    def __init__(self, coordinator, select_type, name, options):
        """Initialize the select entity."""
        self.coordinator = coordinator
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

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Basic {self.coordinator.auth}"}
                
                if self.select_type == "load_mode":
                    value = "1" if option == "Manual" else "2"
                    url = f"http://{self.coordinator.host}/wr_logical.cgi?@426={value}"
                elif self.select_type == "load_1":
                    value = "3" if option == "Disconnected" else "4"
                    url = f"http://{self.coordinator.host}/wr_logical.cgi?@426={value}"
                elif self.select_type == "load_2":
                    value = "5" if option == "Disconnected" else "6"
                    url = f"http://{self.coordinator.host}/wr_logical.cgi?@426={value}"
                elif self.select_type == "exercise_frequency":
                    value = ["0", "1", "2", "3"][["Never", "Weekly", "Bimonthly", "Monthly"].index(option)]
                    url = f"http://{self.coordinator.host}/wr_logical.cgi?@425={value}"
                elif self.select_type == "exercise_day":
                    value = str(["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"].index(option))
                    url = f"http://{self.coordinator.host}/wr_logical.cgi?@391={value}"
                elif self.select_type == "exercise_hour":
                    url = f"http://{self.coordinator.host}/wr_logical.cgi?@392={option}"
                elif self.select_type == "exercise_minute":
                    url = f"http://{self.coordinator.host}/wr_logical.cgi?@393={option}"
                
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        _LOGGER.error(f"Failed to set {self._name}: {response.status}")
                    else:
                        await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error(f"Error setting {self._name}: {err}")

    async def async_update(self):
        """Update the entity."""
        await self.coordinator.async_request_refresh()
