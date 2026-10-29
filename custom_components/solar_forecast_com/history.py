from datetime import datetime, timedelta

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import (
    state_changes_during_period,
)
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util


def _to_kw(state: State) -> float | None:
    """Convert a power sensor state to kilowatts."""
    try:
        value = float(state.state)
    except (ValueError, TypeError):
        return None

    unit = (state.attributes or {}).get("unit_of_measurement")
    if unit in (UnitOfPower.KILO_WATT, "kW"):
        return value
    if unit in (UnitOfPower.MEGA_WATT, "MW"):
        return value * 1000.0
    # Watts, or unknown units (previous behaviour assumed W).
    return value / 1000.0


async def get_power_payload(
    hass: HomeAssistant,
    entity_id: str,
    start_time: datetime | None = None,
) -> dict:
    """Fetch power sensor history and return timestamp -> kW."""

    end_time = dt_util.utcnow()
    if start_time is None:
        start_time = end_time - timedelta(hours=24)

    history = await get_instance(hass).async_add_executor_job(
        state_changes_during_period,
        hass,
        start_time,
        end_time,
        entity_id,
        None,
        True,  # include_start_time
    )

    states = history.get(entity_id, [])
    data = {}

    for state in states:
        power = _to_kw(state)
        if power is None:
            continue
        data[state.last_updated.isoformat()] = power

    return data
