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


def _align_tz(dt: datetime, tz) -> datetime:
    """Make dt comparable with timestamps in tz."""
    if tz is None:
        return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def energy_for_upcoming(forecast: dict, minutes: int) -> float:
    """Energy (kWh) from power samples overlapping (now, now + minutes).

    Each sample is treated as constant power until the next sample (or 15
    minutes for the last point). Overlapping intervals are included
    proportionally.
    """
    if not forecast or minutes <= 0:
        return 0.0

    points = _forecast_points(forecast)
    if not points:
        return 0.0

    tz = next((dt.tzinfo for dt, _pwr in points if dt.tzinfo is not None), None)
    now = _align_tz(local_now(forecast), tz)
    window_end = now + timedelta(minutes=minutes)
    default_interval = timedelta(minutes=15)

    total = 0.0
    for i, (start, power) in enumerate(points):
        start = _align_tz(start, tz)
        if i + 1 < len(points):
            end = _align_tz(points[i + 1][0], tz)
        else:
            end = start + default_interval
        if end <= start:
            continue
        overlap_start = max(start, now)
        overlap_end = min(end, window_end)
        if overlap_end <= overlap_start:
            continue
        hours = (overlap_end - overlap_start).total_seconds() / 3600.0
        total += max(0.0, power) * hours

    return round(total, 2)


def _forecast_points(forecast: dict) -> list[tuple[datetime, float]]:
    """Parse a power series into sorted (datetime, kW) points."""
    points: list[tuple[datetime, float]] = []
    for ts, value in forecast.items():
        dt = _parse_ts(ts)
        if dt is None:
            continue
        try:
            power = float(value)
        except (TypeError, ValueError):
            continue
        if power != power:  # NaN
            continue
        points.append((dt, power))
    points.sort(key=lambda item: item[0])
    return points


def power_forecast_now(forecast: dict) -> float:
    """Forecast power (kW) for the interval that contains now.

    Each sample is held until the next sample (or 15 minutes for the last
    point). Returns 0 when now is outside the forecast window.
    """
    points = _forecast_points(forecast)
    if not points:
        return 0.0

    tz = next((dt.tzinfo for dt, _pwr in points if dt.tzinfo is not None), None)
    now = _align_tz(local_now(forecast), tz)
    default_interval = timedelta(minutes=15)

    for i, (start, power) in enumerate(points):
        start = _align_tz(start, tz)
        if i + 1 < len(points):
            end = _align_tz(points[i + 1][0], tz)
        else:
            end = start + default_interval
        if end <= start:
            continue
        if start <= now < end:
            return round(max(0.0, power), 2)

    return 0.0
