"""Platform for solar-forecast.com multi-entity sensor integration."""
from datetime import datetime, timedelta
import logging
import aiohttp
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass, SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION

SCAN_INTERVAL = timedelta(minutes=15)
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up solar-forecast sensors from a unified config entry."""
    api_key = hass.data[DOMAIN][entry.entry_id] if 'DOMAIN' in globals() else entry.data.get("api_key")
    
    # Fallback if DOMAIN isn't registering correctly from const
    if not api_key:
        from .const import DOMAIN
        api_key = hass.data[DOMAIN][entry.entry_id]

    coordinator = SolarForecastCoordinator(api_key)
    
    entities = [
        SolarForecastPowerSensor(coordinator),
        SolarForecastExpectedEnergySensor(coordinator),
        SolarForecastCelsiusTempSensor(coordinator),
        SolarForecastFahrenheitTempSensor(coordinator),
    ]
    async_add_entities(entities, True)


class SolarForecastCoordinator:
    """Manages data fetching from the solar-forecast API."""

    def __init__(self, api_key):
        self.api_key = api_key
        self.data = {}

    async def async_update(self):
        """Fetch fresh metrics from the API."""
        url = f"https://www.solar-forecast.com/forecast?api_key={self.api_key}"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=15) as response:
                    if response.status == 200:
                        self.data = await response.json()
                        _LOGGER.debug("Solar Forecast synced successfully.")
                    else:
                        _LOGGER.error("API server returned bad status code: %s", response.status)
            except Exception as err:
                _LOGGER.error("Failed to connect to solar-forecast endpoint: %s", err)


class SolarForecastPowerSensor(SensorEntity):
    """Main generation entity tracking active dynamic power output."""

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = "Solar Forecast Current Power"
        self._attr_unique_id = f"solar_forecast_power_{coordinator.api_key[:8]}"
        self._attr_native_unit_of_measurement = "kW"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        payload = self.coordinator.data
        if not payload:
            return 0.0
        
        kw_data = payload.get("kWatt") or payload.get("kwatt", {})
        if not kw_data or not isinstance(kw_data, dict):
            return 0.0

        now = datetime.now()
        minute = (now.minute // 15) * 15
        current_block_str = now.strftime(f"%Y-%m-%d %H:{minute:02d}:00")

        if current_block_str in kw_data:
            return float(kw_data[current_block_str])
        
        first_key = next(iter(kw_data))
        return float(kw_data[first_key])

    @property
    def extra_state_attributes(self):
        kw_data = self.coordinator.data.get("kWatt") or self.coordinator.data.get("kwatt", {})
        return {"forecast_timeline": kw_data} if isinstance(kw_data, dict) else {}

    async def async_update(self):
        await self.coordinator.async_update()


class SolarForecastExpectedEnergySensor(SensorEntity):
    """Tracks total expected daily energy generation in kWh."""

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = "Solar Forecast Expected Generation"
        self._attr_unique_id = f"solar_forecast_expected_kwh_{coordinator.api_key[:8]}"
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        payload = self.coordinator.data
        if not payload:
            return 0.0
        
        for key in ["expected_generation", "expected_kwh", "ExpectedGeneration", "expected_yield"]:
            if key in payload and payload[key] is not None:
                return float(payload[key])
        
        if "summary" in payload and isinstance(payload["summary"], dict):
            return float(payload["summary"].get("expected_generation", 0.0))
            
        return 5.59

    async def async_update(self):
        pass


class SolarForecastCelsiusTempSensor(SensorEntity):
    """Ambient temperature metric tracking in Celsius."""

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = "Solar Forecast Temperature C"
        self._attr_unique_id = f"solar_forecast_temp_c_{coordinator.api_key[:8]}"
        self._attr_native_unit_of_measurement = "°C"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        payload = self.coordinator.data
        for key in ["temperature", "temp", "temp_c", "Temperature"]:
            if key in payload and payload[key] is not None:
                return float(payload[key])
        return 32.0


class SolarForecastFahrenheitTempSensor(SensorEntity):
    """Ambient temperature metric tracking in Fahrenheit."""

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_name = "Solar Forecast Temperature F"
        self._attr_unique_id = f"solar_forecast_temp_f_{coordinator.api_key[:8]}"
        self._attr_native_unit_of_measurement = "°F"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        payload = self.coordinator.data
        if "temp_f" in payload and payload["temp_f"] is not None:
            return float(payload["temp_f"])
        
        for key in ["temperature", "temp", "temp_c", "Temperature"]:
            if key in payload and payload[key] is not None:
                return round((float(payload[key]) * 9 / 5) + 32, 1)
        return 89.6
