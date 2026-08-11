from homeassistant.components import panel_custom
import logging

_LOGGER = logging.getLogger(__name__)


async def async_register_panel(hass):
#    _LOGGER.warning("REGISTERING SOLAR FORECAST PANEL")


    await panel_custom.async_register_panel(
        hass,
        webcomponent_name="solar-forecast-panel",
        frontend_url_path="solar_forecast",
        module_url="solar_forecast/panel.js",
        sidebar_title="Solar Forecast",
        sidebar_icon="mdi:solar-power",
        require_admin=False,
    )
