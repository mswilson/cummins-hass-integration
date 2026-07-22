"""Cummins Generator integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import CONF_HOST
from .client import GeneratorClient
from .sensor import CumminsGeneratorCoordinator

DOMAIN = "cummins_generator"
PLATFORMS = ["sensor", "button", "binary_sensor", "select", "datetime"]

CONF_MIN_REQUEST_GAP_MS = "min_request_gap_ms"
DEFAULT_MIN_REQUEST_GAP_MS = 500


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cummins Generator from a config entry."""
    host = entry.data[CONF_HOST]
    password = entry.data.get("password", "cummins")
    min_gap_ms = entry.options.get(CONF_MIN_REQUEST_GAP_MS, DEFAULT_MIN_REQUEST_GAP_MS)

    client = GeneratorClient(hass, host, password, min_gap_ms)
    coordinator = CumminsGeneratorCoordinator(hass, client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        await client.close()
        raise ConfigEntryNotReady(f"Cannot connect to generator: {err}")

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Apply options changes without a full reload."""
    data = hass.data[DOMAIN][entry.entry_id]
    data["client"].update_min_gap(
        entry.options.get(CONF_MIN_REQUEST_GAP_MS, DEFAULT_MIN_REQUEST_GAP_MS)
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data[DOMAIN].pop(entry.entry_id)
    await data["client"].close()
    return unload_ok
