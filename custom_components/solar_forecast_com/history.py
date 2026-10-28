from datetime import timedelta
import logging
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import (
    state_changes_during_period,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


async def get_power_payload(
    hass: HomeAssistant,
    entity_id: str,
) -> dict:
    """Fetch power sensor history and return the payload."""

    # Calculate time range
    end_time = dt_util.utcnow()
    start_time = end_time - timedelta(hours=24)

    # Fetch history from Home Assistant recorder
    history = await get_instance(hass).async_add_executor_job(
        state_changes_during_period,
        hass,
        start_time,
        end_time,
        entity_id,
        None,
        True,  # include_start_time
        #True,  # significant_changes_only
    )

    states = history.get(entity_id, [])
    _LOGGER.warning("payload: %s",str(states))
    data = {}

    for state in states:
        try:
            power = float(state.state)/1000
        except (ValueError, TypeError):
            continue

        data[state.last_updated.isoformat()]= power
     

    # Construct payload
    payload = data

    return payload
