"""Helpers for converting cumulative generation energy to power."""

from datetime import datetime, timezone
import logging

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

def _parse_energy_points(energy: dict) -> list[tuple[datetime, str, float]]:
    """Parse energy dict into (datetime, original_key, value) sorted by time."""
    points = []

    for ts, value in energy.items():
        try:
            dt = datetime.fromisoformat(str(ts))
            val = float(value)
            if val != val:  # NaN
                continue
            points.append((dt, str(ts), val))
        except (TypeError, ValueError):
            continue

    points.sort(key=lambda item: item[0])
    return points


def energy_to_power(energy: dict) -> dict:
    """Convert cumulative energy (kWh) to interval power (kW).

    Power at each timestamp is (Δenergy / Δtime_hours) over the preceding interval.
    """
    points = _parse_energy_points(energy)
    power = {}

    for i in range(1, len(points)):
        dt_prev, _, e_prev = points[i - 1]
        dt_curr, ts_curr, e_curr = points[i]
        hours = (dt_curr - dt_prev).total_seconds() / 3600.0
        if hours <= 0:
            continue
        power[ts_curr] = (e_curr - e_prev) / hours

    return power


def latest_power(power: dict) -> float:
    """Return the most recent power value (kW), or 0 if empty."""
    points = _parse_energy_points(power)
    if not points:
        return 0.0
    return points[-1][2]


def total_energy_produced(energy: dict) -> float:
    """Energy produced over the series window for a cumulative meter (kWh)."""
    points = _parse_energy_points(energy)
    if len(points) < 2:
        return 0.0
    return points[-1][2] - points[0][2]


def forecast_to_wh_hours(data: dict) -> dict[str, float]:
    """Convert coordinator data to Home Assistant wh_hours format."""
    _LOGGER.warning("energy_db data: %s", data)
    result = {}

    power = data["kWatt"]
    timestamps = data["datetime_utc"]

    for key in sorted(power):
        dt = datetime.fromtimestamp(
            timestamps[key] / 1000,
            tz=timezone.utc,
        )

        # kW × 0.25 h = kWh
        # convert kWh -> Wh
        wh = float(power[key]) * 0.25 * 1000

        result[dt.isoformat()] = round(wh, 2)

    return result

"""Energy platform."""

from homeassistant.core import HomeAssistant

from .coordinator import ForecastCoordinator


async def async_get_solar_forecast(
    hass: HomeAssistant,
    config_entry_id: str,
) -> dict[str, dict[str, float]] | None:
    """Return solar forecast."""

    coordinator = hass.data.get(DOMAIN, {}).get(config_entry_id)

    if coordinator is None:
        return None

    if coordinator.data is None:
        return None

    return {
        "wh_hours": forecast_to_wh_hours(coordinator.data)
    }
