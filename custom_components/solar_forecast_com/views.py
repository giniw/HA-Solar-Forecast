"""HTTP API views for Solar Forecast."""

import logging

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .arrays import array_series_key, normalize_arrays
from .const import DOMAIN
from .energy import latest_power, total_energy_produced
from .forecast_days import energy_for_local_day

_LOGGER = logging.getLogger(__name__)


def _enrich_payload(raw: dict | None) -> dict:
    """Add summary fields used by the panel."""
    data = dict(raw or {})
    forecast = data.get("kWatt", {}) or {}
    arrays = data.get("arrays") or normalize_arrays(data)
    data["arrays"] = arrays

    data["TodaysForecast"] = energy_for_local_day(forecast, day_offset=0)
    data["TomorrowsForecast"] = energy_for_local_day(forecast, day_offset=1)
    data["DayAftersForecast"] = energy_for_local_day(forecast, day_offset=2)

    data["GenerationNow"] = round(
        latest_power(data.get("generation", {}) or {}),
        2,
    )
    data["TotalGeneration"] = round(
        total_energy_produced(data.get("generation_energy", {}) or {}),
        2,
    )

    array_day_totals = []
    for item in arrays:
        num = item["array"]
        series = data.get(array_series_key(num), {}) or {}
        array_day_totals.append(
            {
                "array": num,
                "label": item.get("label", f"Array {num}"),
                "color": item.get("color"),
                "today": energy_for_local_day(series, day_offset=0),
                "tomorrow": energy_for_local_day(series, day_offset=1),
                "day_after": energy_for_local_day(series, day_offset=2),
            }
        )

    data["ArrayDayTotals"] = array_day_totals
    data["Next3Days"] = [
        data["TodaysForecast"],
        data["TomorrowsForecast"],
        data["DayAftersForecast"],
    ]
    return data


class SolarForecastView(HomeAssistantView):
    """Expose forecast data through the Home Assistant REST API."""

    url = "/api/solar_forecast/{entry_id}"
    name = "api:solar_forecast"
    requires_auth = True

    async def get(self, request, entry_id):
        """Handle GET requests."""

        hass: HomeAssistant = request.app["hass"]

        if DOMAIN not in hass.data:
            _LOGGER.error("%s not found in hass.data", DOMAIN)
            return self.json({"error": "Domain not initialized"}, status_code=500)

        if not hass.data[DOMAIN]:
            _LOGGER.error("No config entries found")
            return self.json({"error": "No coordinator"}, status_code=500)

        coordinator = hass.data[DOMAIN].get(entry_id)
        if coordinator is None:
            return self.json({"error": "Unknown entry"}, status_code=404)

        return self.json(_enrich_payload(coordinator.data))


class SolarForecastEntitiesView(HomeAssistantView):
    """Return entity mapping."""

    url = "/api/solar_forecast/entities"
    name = "api:solar_forecast_entities"
    requires_auth = True

    async def get(self, request):

        hass = request.app["hass"]

        registry = er.async_get(hass)

        mapping = {}

        for entry in registry.entities.values():

            if entry.platform != DOMAIN:
                continue

            mapping[entry.unique_id] = entry.entity_id

        return self.json(mapping)


class SolarForecastEntriesView(HomeAssistantView):
    url = "/api/solar_forecast/entries"
    name = "api:solar_forecast_entries"
    requires_auth = True

    async def get(self, request):
        hass = request.app["hass"]

        entries = [
            {
                "entry_id": entry.entry_id,
                "title": entry.title,
            }
            for entry in hass.config_entries.async_entries(DOMAIN)
        ]

        return self.json(entries)
