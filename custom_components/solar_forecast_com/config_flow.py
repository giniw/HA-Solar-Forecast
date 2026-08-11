import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY,CONF_NAME

from .api import validate_api_key, AuthenticationError
from .const import API_URL, DOMAIN


class SolarForecastConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    async def async_step_user(self, user_input=None):

        errors = {}

        if user_input is not None:

            api_key = user_input[CONF_API_KEY]
            identifier=user_input[CONF_NAME]
            title=identifier

            try:

                await validate_api_key(
                    self.hass,
                    API_URL,
                    api_key,
                )

            except AuthenticationError:
                errors["base"] = "invalid_auth"

            except Exception:
                errors["base"] = "cannot_connect"

            else:

               # await self.async_set_unique_id(api_key)
               # self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=title,
                    data=user_input,
                    
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_NAME): str,
                }
            ),
            errors=errors,
        )
