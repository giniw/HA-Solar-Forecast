"""Helpers for converting cumulative generation energy to power."""

from datetime import datetime, timezone
import logging

from .const import CONF_USE_PERSONALISED, DOMAIN


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
        # Bad meter resets / out-of-order uploads can yield negative Δenergy.
        power[ts_curr] = max(0.0, (e_curr - e_prev) / hours)

    return power


def power_to_energy(power: dict) -> dict:
    """Integrate instantaneous power (kW) to cumulative energy (kWh).

    Each sample is held until the next timestamp (rectangular integration).
    """
    points = _parse_energy_points(power)
    energy = {}
    cumulative = 0.0

    for i, (dt, ts, _val) in enumerate(points):
        if i > 0:
            dt_prev, _, p_prev = points[i - 1]
            hours = (dt - dt_prev).total_seconds() / 3600.0
            if hours > 0:
                cumulative += max(0.0, p_prev) * hours
        energy[ts] = cumulative

    return energy


def latest_power(power: dict) -> float:
    """Return the most recent power value (kW), or 0 if empty."""
    points = _parse_energy_points(power)
    if not points:
        return 0.0
    return max(0.0, points[-1][2])


def total_energy_produced(energy: dict) -> float:
    """Energy produced over the series window for a cumulative meter (kWh)."""
    points = _parse_energy_points(energy)
    if len(points) < 2:
        return 0.0
    return points[-1][2] - points[0][2]


def has_personalised_forecast(data: dict | None) -> bool:
    """Return True when personalised_kWatt has at least one sample."""
    series = (data or {}).get("personalised_kWatt") or {}
    return isinstance(series, dict) and len(series) > 0


def selected_forecast_power(data: dict | None, use_personalised: bool) -> dict:
    """Return the power series used for Energy dashboard / day totals."""
    payload = data or {}
    if use_personalised:
        series = payload.get("personalised_kWatt") or {}
        if isinstance(series, dict) and series:
            return series
    return payload.get("kWatt") or {}


def _wh_timestamp(key, timestamps: dict) -> datetime | None:
    """Resolve a series key to a UTC datetime."""
    if timestamps and key in timestamps:
        try:
            return datetime.fromtimestamp(
                timestamps[key] / 1000,
                tz=timezone.utc,
            )
        except (TypeError, ValueError, OSError, OverflowError):
            pass
    try:
        dt = datetime.fromisoformat(str(key))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def forecast_to_wh_hours(
    data: dict,
    use_personalised: bool = False,
) -> dict[str, float]:
    """Convert coordinator data to Home Assistant wh_hours format."""
    _LOGGER.warning("energy_db data: %s", data)
    result = {}

    power = selected_forecast_power(data, use_personalised)
    timestamps = data.get("datetime_utc") or {}

    for key in sorted(power):
        dt = _wh_timestamp(key, timestamps)
        if dt is None:
            continue
        try:
            # kW × 0.25 h = kWh, then kWh -> Wh
            wh = float(power[key]) * 0.25 * 1000
        except (TypeError, ValueError):
            continue
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

    use_personalised = bool(
        coordinator.entry.options.get(CONF_USE_PERSONALISED, False)
    )
    return {
        "wh_hours": forecast_to_wh_hours(
            coordinator.data,
            use_personalised=use_personalised,
        )
    }
