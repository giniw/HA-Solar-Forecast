import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.helpers import selector

from .api import AuthenticationError, validate_api_key
from .const import (
    API_URL,
    CONF_POWER_SENSOR,
    CONF_SEND_GENERATION,
    DOMAIN,
    send_generation_enabled,
)

_POWER_SENSOR_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(
        domain="sensor",
        device_class="power",
    )
)


def _schema(
    defaults: dict | None = None,
    *,
    include_credentials: bool = True,
) -> vol.Schema:
    defaults = defaults or {}
    schema: dict = {}

    if include_credentials:
        api_key = vol.Required(CONF_API_KEY)
        name = vol.Required(CONF_NAME)
        if CONF_API_KEY in defaults:
            api_key = vol.Required(CONF_API_KEY, default=defaults[CONF_API_KEY])
        if CONF_NAME in defaults:
            name = vol.Required(CONF_NAME, default=defaults[CONF_NAME])
        schema[api_key] = str
        schema[name] = str

    sensor = vol.Optional(CONF_POWER_SENSOR)
    if defaults.get(CONF_POWER_SENSOR):
        sensor = vol.Optional(
            CONF_POWER_SENSOR, default=defaults[CONF_POWER_SENSOR]
        )
    schema[sensor] = _POWER_SENSOR_SELECTOR

    schema[
        vol.Required(
            CONF_SEND_GENERATION,
            default=bool(defaults.get(CONF_SEND_GENERATION, False)),
        )
    ] = selector.BooleanSelector()
    return vol.Schema(schema)


def _with_generation_fields(base: dict, user_input: dict) -> dict:
    data = dict(base)
    if user_input.get(CONF_POWER_SENSOR):
        data[CONF_POWER_SENSOR] = user_input[CONF_POWER_SENSOR]
    else:
        data.pop(CONF_POWER_SENSOR, None)
    data[CONF_SEND_GENERATION] = bool(user_input.get(CONF_SEND_GENERATION, False))
    return data


class SolarForecastConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    async def async_step_user(self, user_input=None):

        errors = {}

        if user_input is not None:

            api_key = user_input[CONF_API_KEY]
            identifier = user_input[CONF_NAME]
            title = identifier

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
                return self.async_create_entry(
                    title=title,
                    data=_with_generation_fields(
                        {
                            CONF_API_KEY: api_key,
                            CONF_NAME: identifier,
                        },
                        user_input,
                    ),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return SolarForecastOptionsFlow(config_entry)


class SolarForecastOptionsFlow(config_entries.OptionsFlow):
    """Allow changing the production sensor and upload checkbox later."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self._entry,
                data=_with_generation_fields(self._entry.data, user_input),
            )
            return self.async_create_entry(title="", data={})

        defaults = dict(self._entry.data)
        defaults[CONF_SEND_GENERATION] = send_generation_enabled(self._entry)
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(defaults, include_credentials=False),
        )
