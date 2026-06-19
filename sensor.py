import aiohttp
from datetime import timedelta
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass, SensorEntity
from homeassistant.const import UnitOfEnergy
from .const import DOMAIN

SCAN_INTERVAL = timedelta(minutes=30) # How often to fetch predictions

async def async_setup_entry(hass, entry, async_add_entities):
    """Add sensors for the integration config entry."""
    api_key = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SolarForecastPredictionSensor(api_key)], True)

class SolarForecastPredictionSensor(SensorEntity):
    """Representation of the Prediction Sensor."""

    def __init__(self, api_key):
        self._api_key = api_key
        self._attr_name = "Solar Forecast Prediction"
        self._attr_unique_id = f"solar_forecast_{api_key[:6]}"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILOWATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._state = None
        self._attributes = {}

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        """This passes the future hourly prediction list into the attributes for graphing."""
        return self._attributes

    async def async_update(self):
        """Fetch data from your website's api."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"https://solar-forecast.com/api/v1/data?key={self._api_key}") as response:
                    if response.status == 200:
                        data = await response.json()
                        # Assuming your API returns total expected production for the day
                        self._state = data.get("total_production")
                        # Pass raw hourly prediction arrays for custom dashboard graphs
                        self._attributes = {"detailed_forecast": data.get("hourly_breakdown")}
            except Exception:
                pass
