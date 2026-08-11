"""Day totals for forecast power series using site-local calendar dates."""

from datetime import date, datetime, timedelta

from homeassistant.util import dt as dt_util


def _parse_ts(ts) -> datetime | None:
    try:
        return datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None


def series_tzinfo(series: dict):
    """Return tzinfo from the first timezone-aware timestamp in series, if any."""
    for ts in series:
        parsed = _parse_ts(ts)
        if parsed is not None and parsed.tzinfo is not None:
            return parsed.tzinfo
    return None


def local_now(series: dict | None = None) -> datetime:
    """Current time in the same local frame as forecast/generation JSON keys.

    Prefer the timezone embedded in the series timestamps; otherwise use the
    Home Assistant configured local timezone (not the host's naive datetime.now()).
    """
    tz = series_tzinfo(series) if series else None
    if tz is not None:
        return datetime.now(tz)
    return dt_util.now()


def local_today(series: dict | None = None) -> date:
    """Calendar 'today' aligned with the JSON keys' local datetime."""
    return local_now(series).date()


def energy_for_local_day(forecast: dict, day_offset: int = 0) -> float:
    """Sum 15-minute power (kW) into energy (kWh) for local today + offset."""
    if not forecast:
        return 0.0

    target = local_today(forecast) + timedelta(days=day_offset)
    total = 0.0

    for ts, value in forecast.items():
        dt = _parse_ts(ts)
        if dt is None:
            continue
        try:
            if dt.date() == target:
                total += float(value)
        except (TypeError, ValueError):
            continue

    return round(total * 0.25, 2)
