"""Platform for solar-forecast.com multi-entity sensor integration."""
from datetime import timedelta
import logging
import aiohttp

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass, SensorEntity
from homeassistant.const import PERCENTAGE
from .const import DOMAIN

# 20-minute scan interval safely honors your 15-call rate limit
SCAN_INTERVAL = timedelta(minutes=20)
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up all solar-forecast sensors from a unified config entry."""
    api_key = hass.data[DOMAIN][entry.entry_id]
    
    # Initialize the core data coordinator entity
    main_power_sensor = SolarForecastPowerSensor(api_key)
    
    # Generate companion helper metrics entities linking back to the same data context
    companion_entities = [
        SolarForecastLatitudeSensor(api_key, main_power_sensor),
        SolarForecastLongitudeSensor(api_key, main_power_sensor),
        SolarForecastCelsiusTempSensor(api_key, main_power_sensor),
        SolarForecastFahrenheitTempSensor(api_key, main_power_sensor),
    ]
    
    async_add_entities([main_power_sensor] + companion_entities, True)


class SolarForecastPowerSensor(SensorEntity):
    """Core Power sensor that fetches data and handles attribute mapping for graphs."""

    def __init__(self, api_key):
        """Initialize the main power sensor parameters."""
        self._api_key = api_key
        self._attr_name = "Solar Forecast Current Power"
        self._attr_unique_id = f"solar_forecast_power_{api_key[:8]}"
        self._attr_native_unit_of_measurement = "kW"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        
        self._state = None
        self._extra_attributes = {}
        self.raw_payload = {}  # Shared cache container for companion helper entities

    @property
    def state(self):
        """Return the current electrical output state."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return raw time data properties for frontend apex-charts/mini-graph cards."""
        return self._extra_attributes

    async def async_update(self):
        """Fetch fresh forecast metrics directly from your web server API."""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"https://www.solar-forecast.com/forecast?api_key={self._api_key}"
                async with session.get(url, timeout=15) as response:
                    if response.status == 200:
                        self.raw_payload = await response.json()
                        
                        # Process the time-series array for graphing
                        kw_data = self.raw_payload.get("kWatt", {})
                        if kw_data:
                            first_time_key = next(iter(kw_data))
                            self._state = float(kw_data[first_time_key])
                            
                            # Push full nested dictionary array into state attributes
                            self._extra_attributes = {"forecast_timeline": kw_data}
                        else:
                            _LOGGER.warning("kWatt power generation timeline payload was empty.")
                    else:
                        _LOGGER.error("Failed data query sync from Solar-Forecast server: HTTP %s", response.status)
            except Exception as err:
                _LOGGER.error("Communication pipeline exception on update routine: %s", err)


class SolarForecastLatitudeSensor(SensorEntity):
    """Latitude coordinates entry entity."""
    def __init__(self, api_key, coordinator):
        self._coordinator = coordinator
        self._attr_name = "Solar Forecast Latitude"
        self._attr_unique_id = f"solar_forecast_lat_{api_key[:8]}"

    @property
    def state(self):
        # Dynamically grabs standard naming variants 'latitude' or 'lat' from your root JSON
        return self._coordinator.raw_payload.get("latitude") or self._coordinator.raw_payload.get("lat", "Unknown")


class SolarForecastLongitudeSensor(SensorEntity):
    """Longitude coordinates entry entity."""
    def __init__(self, api_key, coordinator):
        self._coordinator = coordinator
        self._attr_name = "Solar Forecast Longitude"
        self._attr_unique_id = f"solar_forecast_lon_{api_key[:8]}"

    @property
    def state(self):
        return self._coordinator.raw_payload.get("longitude") or self._coordinator.raw_payload.get("lon", "Unknown")


class SolarForecastCelsiusTempSensor(SensorEntity):
    """Ambient temperature entity tracking in Celsius."""
    def __init__(self, api_key, coordinator):
        self._coordinator = coordinator
        self._attr_name = "Solar Forecast Temperature C"
        self._attr_unique_id = f"solar_forecast_temp_c_{api_key[:8]}"
        self._attr_native_unit_of_measurement = "°C"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def state(self):
        # Extracts raw Celsius field from your web panel configuration dictionary
        val = self._coordinator.raw_payload.get("temperature") or self._coordinator.raw_payload.get("temp_c")
        return float(val) if val is not None else None


class SolarForecastFahrenheitTempSensor(SensorEntity):
    """Ambient temperature entity tracking in Fahrenheit."""
    def __init__(self, api_key, coordinator):
        self._coordinator = coordinator
        self._attr_name = "Solar Forecast Temperature F"
        self._attr_unique_id = f"solar_forecast_temp_f_{api_key[:8]}"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def state(self):
        # Pulls 'temp_f' directly if outputted, fallback converts Celsius dynamically via logic formula (C * 9/5) + 32
        payload = self._coordinator.raw_payload
        if "temp_f" in payload:
            return float(payload["temp_f"])
        
        c_val = payload.get("temperature") or payload.get("temp_c")
        if c_val is not None:
            return round((float(c_val) * 9 / 5) + 32, 2)
        return None
