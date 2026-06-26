"""The Solar-Forecast.com integration entry point."""
import logging
import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Solar-Forecast.com component (legacy YAML fallback)."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solar-Forecast.com from a modern UI config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Store the API key associated with this configuration entry instance
    api_key = entry.data["api_key"]
    hass.data[DOMAIN][entry.entry_id] = api_key

    # Define the service logic routine
    async def handle_record_generation(call: ServiceCall):
        """Extract inputs and POST generation data directly to the server."""
        energy = call.data.get("energy")
        datetime_val = call.data.get("datetime")
        
        # Build the exact endpoint string specified by your API documentation
        url = f"https://www.solar-forecast.com/generation?api_key={api_key}&energy={energy}"
        if datetime_val:
            url += f"&datetime={datetime_val}"
            
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, timeout=15) as response:
                    if response.status == 200:
                        _LOGGER.info("Successfully uploaded generation metrics: %s kWh", energy)
                    else:
                        _LOGGER.error("Failed to post generation data. Server returned HTTP %s", response.status)
            except Exception as err:
                _LOGGER.error("Network exception encountered during generation post: %s", err)

    # Formally register the action with Home Assistant core execution engine
    hass.services.async_register(
        DOMAIN, "record_generation", handle_record_generation
    )

    # Forward token references to load sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and clean up associated background hooks."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        # Unregister the service when the integration instance is removed
        hass.services.async_remove(DOMAIN, "record_generation")
    return unload_ok
