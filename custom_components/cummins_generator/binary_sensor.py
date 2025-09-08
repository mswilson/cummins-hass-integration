"""Cummins Generator binary sensor platform."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.const import CONF_HOST
from homeassistant.helpers.entity import DeviceInfo
from .sensor import CumminsGeneratorCoordinator

DOMAIN = "cummins_generator"

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Cummins Generator binary sensors."""
    coordinator = hass.data["cummins_generator"][config_entry.entry_id]
    
    binary_sensors = [
        CumminsGeneratorBinarySensor(coordinator, "utility_present", "Utility Present", 0x01),
        CumminsGeneratorBinarySensor(coordinator, "utility_connected", "Utility Connected", 0x02),
        CumminsGeneratorBinarySensor(coordinator, "genset_running", "Genset Running", 0x0C),
        CumminsGeneratorBinarySensor(coordinator, "standby_disabled", "Standby Disabled", 0x10),
        CumminsGeneratorBinarySensor(coordinator, "action_required", "Action Required", 0x60),
    ]
    async_add_entities(binary_sensors)

class CumminsGeneratorBinarySensor(BinarySensorEntity):
    """Representation of a Cummins Generator binary sensor."""

    def __init__(self, coordinator, sensor_type, name, mask):
        """Initialize the binary sensor."""
        self.coordinator = coordinator
        self.sensor_type = sensor_type
        self._name = name
        self.mask = mask
        self._attr_unique_id = f"{coordinator.host}_{sensor_type}"
        if sensor_type == "action_required":
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        elif sensor_type == "utility_present":
            self._attr_device_class = BinarySensorDeviceClass.POWER
        elif sensor_type == "genset_running":
            self._attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def name(self):
        """Return the name of the binary sensor."""
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
    def is_on(self):
        """Return true if the binary sensor is on."""
        if not self.coordinator.data:
            return False
        lcd_status = self.coordinator.data.get("lcd_status", 0)
        return bool(lcd_status & self.mask)

    @property
    def available(self):
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_update(self):
        """Update the entity."""
        await self.coordinator.async_request_refresh()
