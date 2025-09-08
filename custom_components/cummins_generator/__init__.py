"""Cummins Generator integration."""
import aiohttp
import base64
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import CONF_HOST
from .sensor import CumminsGeneratorCoordinator

DOMAIN = "cummins_generator"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cummins Generator from a config entry."""
    host = entry.data[CONF_HOST]
    password = entry.data.get("password", "cummins")
    
    # Create shared coordinator
    coordinator = CumminsGeneratorCoordinator(hass, host, password)
    
    # Test connectivity
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(f"Cannot connect to generator: {err}")
    
    # Store coordinator for platforms to use
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "button", "binary_sensor", "select"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, ["sensor", "button", "binary_sensor", "select"])
