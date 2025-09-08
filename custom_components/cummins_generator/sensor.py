"""Cummins Generator sensor platform."""
import asyncio
import aiohttp
import base64
import logging
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import CONF_HOST
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity import DeviceInfo

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=30)
DOMAIN = "cummins_generator"

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Cummins Generator sensors."""
    coordinator = hass.data["cummins_generator"][config_entry.entry_id]
    
    sensors = [
        CumminsGeneratorSensor(coordinator, "status", "Status"),
        CumminsGeneratorSensor(coordinator, "battery_voltage", "Battery Voltage", "V"),
        CumminsGeneratorSensor(coordinator, "output_voltage", "Output Voltage", "V"),
        CumminsGeneratorSensor(coordinator, "frequency", "Frequency", "Hz"),
        CumminsGeneratorSensor(coordinator, "engine_hours", "Engine Hours", "h"),
        CumminsGeneratorSensor(coordinator, "load_1", "Load Line 1", "%"),
        CumminsGeneratorSensor(coordinator, "load_2", "Load Line 2", "%"),
    ]
    async_add_entities(sensors)

class CumminsGeneratorCoordinator(DataUpdateCoordinator):
    """Data coordinator for Cummins Generator."""

    def __init__(self, hass, host, password):
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name="Cummins Generator", update_interval=SCAN_INTERVAL)
        self.host = host
        self.auth = base64.b64encode(f"admin:{password}".encode()).decode("ascii")

    async def _async_update_data(self):
        """Fetch data from the generator."""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Basic {self.auth}"}
                async with session.get(f"http://{self.host}/index_data.html", headers=headers) as response:
                    if response.status == 200:
                        data = await response.text()
                        return self._parse_data(data)
                    else:
                        raise UpdateFailed(f"Error fetching data: {response.status}")
        except Exception as err:
            raise UpdateFailed(f"Error communicating with generator: {err}")

    def _parse_data(self, data):
        """Parse the generator data."""
        lines = data.strip().split('\n')
        if len(lines) < 18:
            return {}
        
        status_map = {
            0: "Stopped", 1: "Stopped", 2: "Starting", 3: "Starting",
            4: "Running", 5: "Priming", 6: f"Fault {lines[14]}", 7: "Eng.Only",
            8: "TestMode", 9: "Volt Adj", 20: "Config Mode", 21: "Cycle crank pause",
            22: "Exercising", 23: "Engine Cooldown"
        }
        
        return {
            "status": status_map.get(int(lines[4]), f"Unknown {lines[4]}"),
            "battery_voltage": float(lines[3]) / 10,
            "output_voltage": int(lines[7]),
            "frequency": int(lines[8]),
            "engine_hours": round(int(lines[9]) / 6) / 10,
            "load_1": int(lines[5]),
            "load_2": int(lines[6]),
            "lcd_status": int(lines[13]),
        }

class CumminsGeneratorSensor(SensorEntity):
    """Representation of a Cummins Generator sensor."""

    def __init__(self, coordinator, sensor_type, name, unit=None):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.sensor_type = sensor_type
        self._name = name
        self._unit = unit
        self._attr_unique_id = f"{coordinator.host}_{sensor_type}"
        if sensor_type in ["battery_voltage", "output_voltage"]:
            self._attr_device_class = SensorDeviceClass.VOLTAGE
        elif sensor_type == "frequency":
            self._attr_device_class = SensorDeviceClass.FREQUENCY
        elif sensor_type == "engine_hours":
            self._attr_device_class = SensorDeviceClass.DURATION
        if sensor_type == "battery_voltage":
            self._attr_suggested_display_precision = 1

    @property
    def name(self):
        """Return the name of the sensor."""
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
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get(self.sensor_type)

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_update(self):
        """Update the entity."""
        await self.coordinator.async_request_refresh()
