"""Cummins Generator sensor platform."""
import logging
from datetime import datetime, timedelta
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.entity import DeviceInfo

from .datetime import signal_time_read

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=30)
DOMAIN = "cummins_generator"

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Cummins Generator sensors."""
    data = hass.data["cummins_generator"][config_entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]

    sensors = [
        CumminsGeneratorSensor(coordinator, "status", "Status"),
        CumminsGeneratorSensor(coordinator, "battery_voltage", "Battery Voltage", "V"),
        CumminsGeneratorSensor(coordinator, "output_voltage", "Output Voltage", "V"),
        CumminsGeneratorSensor(coordinator, "frequency", "Frequency", "Hz"),
        CumminsGeneratorSensor(coordinator, "engine_hours", "Engine Hours", "h"),
        CumminsGeneratorSensor(coordinator, "load_1", "Load Line 1", "%"),
        CumminsGeneratorSensor(coordinator, "load_2", "Load Line 2", "%"),
        CumminsGeneratorTimeDriftSensor(client.host),
    ]
    async_add_entities(sensors)

class CumminsGeneratorCoordinator(DataUpdateCoordinator):
    """Data coordinator for Cummins Generator."""

    def __init__(self, hass, client):
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name="Cummins Generator", update_interval=SCAN_INTERVAL)
        self.client = client
        self.host = client.host

    async def _async_update_data(self):
        """Fetch data from the generator."""
        try:
            data = await self.client.get("/index_data.html")
            return self._parse_data(data)
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

class CumminsGeneratorSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Cummins Generator sensor."""

    def __init__(self, coordinator, sensor_type, name, unit=None):
        """Initialize the sensor."""
        super().__init__(coordinator)
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
    def native_value(self):
        """Return the current sensor value."""
        return self.coordinator.data.get(self.sensor_type)

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit


class CumminsGeneratorTimeDriftSensor(SensorEntity):
    """Signed minutes representing the difference between the generator
    clock and HA's clock.

    The generator only reports date/time to minute precision, so the
    raw delta is rounded to the nearest whole minute.
    """

    _attr_should_poll = False
    _attr_native_unit_of_measurement = "min"
    _attr_suggested_display_precision = 0

    def __init__(self, host):
        self._host = host
        self._attr_unique_id = f"{host}_time_drift"
        self._value: int | None = None

    @property
    def name(self):
        return "Cummins Generator Time Drift"

    @property
    def native_value(self):
        return self._value

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self._host)},
            name="Cummins Generator",
            manufacturer="Cummins",
            model="Generator",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_time_read(self._host), self._handle_read
            )
        )

    @callback
    def _handle_read(self, generator_utc: datetime, ha_utc: datetime) -> None:
        ha_minute = ha_utc.replace(second=0, microsecond=0)
        self._value = round((generator_utc - ha_minute).total_seconds() / 60)
        self.async_write_ha_state()
