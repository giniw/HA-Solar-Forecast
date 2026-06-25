"""Platform for sensor integration."""
from datetime import timedelta
import logging
import aiohttp

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass, SensorEntity
from .const import DOMAIN

# Adjusted to 20 minutes to safely stay within your 15-call limit
SCAN_INTERVAL = timedelta(minutes=20)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform from a config entry."""
    api_key = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SolarForecastPowerSensor(api_key)], True)


class SolarForecastPowerSensor(SensorEntity):
    """Representation of a Solar-Forecast.com prediction entity."""

    def __init__(self, api_key):
        """Initialize the sensor properties."""
        self._api_key = api_key
        self._attr_name = "Solar Forecast Current Power"
        self._attr_unique_id = f"solar_forecast_power_{api_key[:8]}"
        
        # Hardcoding the native unit string avoids version-mismatch enum bugs
        self._attr_native_unit_of_measurement = "kW"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        
        self._state = None
        self._extra_attributes = {}

    @property
    def state(self):
        """Return the current numerical reading of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return raw breakdown attributes for graphing."""
        return self._extra_attributes

    async def async_update(self):
        """Fetch fresh forecast metrics directly from your web server API."""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"https://www.solar-forecast.com/forecast?api_key={self._api_key}"
                async with session.get(url, timeout=15) as response:
                    if response.status == 200:
                        json_payload = await response.json()
                        
                        # Grab the "kWatt" nested dictionary block from your API layout
                        kw_data = json_payload.get("kWatt", {})
                        
                        if kw_data:
                            # Set the main entity state to the first/most immediate prediction point
                            first_time_key = next(iter(kw_data))
                            self._state = float(kw_data[first_time_key])
                            
                            # Push the entire timeline into attributes so custom cards can graph them
                            self._extra_attributes = {"forecast_timeline": kw_data}
                        else:
                            _LOGGER.warning("Solar-Forecast data payload was empty or formatted incorrectly.")
                    else:
                        _LOGGER.error("Failed to fetch data from Solar-Forecast: HTTP %s", response.status)
            except Exception as err:
                _LOGGER.error("Error communicating with Solar-Forecast server: %s", err)
