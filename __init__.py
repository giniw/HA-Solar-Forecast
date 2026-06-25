"""The Solar-Forecast.com integration entry point."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Solar-Forecast.com component via legacy YAML (not used, but required as fallback)."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solar-Forecast.com from a modern UI config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Store the validated API key in memory
    hass.data[DOMAIN][entry.entry_id] = entry.data["api_key"]

    # Forward the setup routine to our sensor platform file
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry when the user deletes the integration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
