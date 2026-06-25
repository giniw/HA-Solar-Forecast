"""Config flow for Solar-Forecast.com integration."""
import logging
import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class SolarForecastConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar-Forecast.com."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step when a user adds the integration via UI."""
        errors = {}

        if user_input is not None:
            api_key = user_input["api_key"]
            
            async with aiohttp.ClientSession() as session:
                try:
                    # Target the exact URL format specified in your documentation
                    url = f"https://www.solar-forecast.com/forecast?api_key={api_key}"
                    
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            return self.async_create_entry(
                                title="Solar-Forecast.com", 
                                data={"api_key": api_key}
                            )
                        elif response.status in (401, 403):
                            errors["base"] = "invalid_auth"
                        else:
                            _LOGGER.error("Server returned status code: %s", response.status)
                            errors["base"] = "cannot_connect"
                            
                except aiohttp.ClientError:
                    errors["base"] = "cannot_connect"
                except Exception as err:  # pylint: disable=broad-except
                    _LOGGER.error("Unexpected authentication exception: %s", err)
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("api_key"): str,
            }),
            errors=errors,
        )
