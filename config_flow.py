import vol_schema as vol  # Home assistant configuration schemas
import voluptuous as vol
import aiohttp
from homeassistant import config_entries
from .const import DOMAIN

class SolarForecastConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar-Forecast.com."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """First step when a user adds the integration via UI."""
        errors = {}

        if user_input is not None:
            api_key = user_input["api_key"]
            
            # Validate the API key against your live website api
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(
                        f"https://solar-forecast.com/api/v1/validate?key={api_key}"
                    ) as response:
                        if response.status == 200:
                            return self.async_create_entry(
                                title="Solar Forecast Account", 
                                data={"api_key": api_key}
                            )
                        else:
                            errors["base"] = "invalid_auth"
                except Exception:
                    errors["base"] = "cannot_connect"

        # Show the form to the user if no input or if validation failed
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("api_key"): str,
            }),
            errors=errors,
        )
