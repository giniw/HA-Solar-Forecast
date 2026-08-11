from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .arrays import array_series_key, normalize_arrays
from .const import DOMAIN
from .energy import latest_power, total_energy_produced
from .forecast_days import energy_for_local_day
import logging

_LOGGER = logging.getLogger(__name__)


def _device_info(coordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={
            (DOMAIN, coordinator.entry.entry_id),
        },
        name=coordinator.entry.title,
        manufacturer="Giniw Technologies",
        model="Solar Forecast",
        sw_version="1.1.0",
    )


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the forecast sensor."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data or {}
    arrays = data.get("arrays") or normalize_arrays(data)

    entities = [
        TodayForecastSensor(coordinator),
        TomorrowForecastSensor(coordinator),
        DayAfterForecastSensor(coordinator),
        GenerationSensor(coordinator),
        TotalGenerationSensor(coordinator),
    ]

    for item in arrays:
        num = item["array"]
        entities.append(ArrayTodayForecastSensor(coordinator, num))
        entities.append(ArrayTomorrowForecastSensor(coordinator, num))
        entities.append(ArrayDayAfterForecastSensor(coordinator, num))

    async_add_entities(entities)


class TodayForecastSensor(CoordinatorEntity, SensorEntity):

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_should_poll = False
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_today"
        self._attr_name = "Todays Forecast Sensor"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return energy_for_local_day(
            self.coordinator.data.get("kWatt", {}),
            day_offset=0,
        )

    @property
    def device_info(self):
        return _device_info(self.coordinator)


class TomorrowForecastSensor(CoordinatorEntity, SensorEntity):

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_should_poll = False
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_tomorrow"
        self._attr_name = "Tomorrows Forecast Sensor"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return energy_for_local_day(
            self.coordinator.data.get("kWatt", {}),
            day_offset=1,
        )

    @property
    def device_info(self):
        return _device_info(self.coordinator)


class DayAfterForecastSensor(CoordinatorEntity, SensorEntity):

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_should_poll = False
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_day_after"
        self._attr_name = "Day Afters Forecast Sensor"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return energy_for_local_day(
            self.coordinator.data.get("kWatt", {}),
            day_offset=2,
        )

    @property
    def device_info(self):
        return _device_info(self.coordinator)


class GenerationSensor(CoordinatorEntity, SensorEntity):

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_should_poll = False
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_gen_now"
        self._attr_name = "Generation Now"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return round(
            latest_power(self.coordinator.data.get("generation", {})),
            2,
        )

    @property
    def device_info(self):
        return _device_info(self.coordinator)


class TotalGenerationSensor(CoordinatorEntity, SensorEntity):

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_should_poll = False
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_total_gen"
        self._attr_name = "Total Generation"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return round(
            total_energy_produced(
                self.coordinator.data.get("generation_energy", {})
            ),
            2,
        )

    @property
    def device_info(self):
        return _device_info(self.coordinator)


class _ArrayDayEnergySensor(CoordinatorEntity, SensorEntity):
    """Base sensor for one array's day energy total."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_should_poll = False
    _attr_suggested_display_precision = 2

    _day_offset: int = 0
    _uid_suffix: str = "today"
    _name_prefix: str = "Todays"

    def __init__(self, coordinator, array_num: int):
        super().__init__(coordinator)
        self._array_num = array_num
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_array_{array_num}_{self._uid_suffix}"
        )
        self._attr_name = f"{self._name_prefix} Array {array_num} Forecast"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        key = array_series_key(self._array_num)
        return energy_for_local_day(
            self.coordinator.data.get(key, {}),
            day_offset=self._day_offset,
        )

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        meta = next(
            (a for a in data.get("arrays", []) if a.get("array") == self._array_num),
            {"array": self._array_num},
        )
        return {
            "array": self._array_num,
            "capacity_kw": meta.get("capacity_kw"),
            "tilt": meta.get("tilt"),
            "orientation": meta.get("orientation"),
        }

    @property
    def device_info(self):
        return _device_info(self.coordinator)


class ArrayTodayForecastSensor(_ArrayDayEnergySensor):
    _day_offset = 0
    _uid_suffix = "today"
    _name_prefix = "Todays"


class ArrayTomorrowForecastSensor(_ArrayDayEnergySensor):
    _day_offset = 1
    _uid_suffix = "tomorrow"
    _name_prefix = "Tomorrows"


class ArrayDayAfterForecastSensor(_ArrayDayEnergySensor):
    _day_offset = 2
    _uid_suffix = "day_after"
    _name_prefix = "Day Afters"
