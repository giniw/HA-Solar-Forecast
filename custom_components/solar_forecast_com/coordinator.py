from datetime import timedelta
import logging

from aiohttp import ClientError

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .arrays import normalize_arrays
from .const import (
    API_URL,
    API_URL_GENERATION,
    CONF_POWER_SENSOR,
    DOMAIN,
    send_generation_enabled,
)
from .energy import energy_to_power, power_to_energy
from .history import get_power_payload

_LOGGER = logging.getLogger(__name__)


class ForecastCoordinator(DataUpdateCoordinator):

    def __init__(self, hass, api_key, entry):
        self.api_key = api_key
        self.params = {
            "api_key": api_key,
        }
        self.entry = entry

        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=15),
        )

    @property
    def power_sensor(self):
        return self.entry.data.get(CONF_POWER_SENSOR)

    @property
    def send_generation(self) -> bool:
        return send_generation_enabled(self.entry)

    async def _async_update_data(self):
        session = async_get_clientsession(self.hass)

        try:
            async with session.get(API_URL, params=self.params) as response:
                response.raise_for_status()
                data = await response.json()

                if not isinstance(data, dict):
                    raise UpdateFailed("Unexpected forecast response")

                if "personalised_kWatt" not in data:
                    data["personalised_kWatt"] = {}

                if "system_info" not in data or not isinstance(
                    data.get("system_info"), dict
                ):
                    data["system_info"] = {"arrays": []}

                data["arrays"] = normalize_arrays(data)

            if self.send_generation:
                await self._async_upload_and_fetch_generation(session, data)
            else:
                await self._async_load_local_generation(data)

            return data

        except ClientError as err:
            raise UpdateFailed(err) from err

    async def _async_upload_and_fetch_generation(self, session, data: dict) -> None:
        """Upload local history (if configured), then read generation from the API."""
        if self.power_sensor:
            payload = await get_power_payload(self.hass, self.power_sensor)
            async with session.post(
                API_URL_GENERATION,
                params=self.params,
                json=payload,
            ) as response:
                response.raise_for_status()

        async with session.get(
            API_URL_GENERATION, params=self.params
        ) as response:
            response.raise_for_status()
            data_gen = await response.json()

            if isinstance(data_gen, dict) and "energy_kWh" in data_gen:
                energy = data_gen.get("energy_kWh") or {}
                data["generation_energy"] = energy
                data["generation"] = energy_to_power(energy)
            else:
                data["generation_energy"] = {}
                data["generation"] = {}

    async def _async_load_local_generation(self, data: dict) -> None:
        """Fill generation from Home Assistant sensor history (no cloud upload)."""
        if not self.power_sensor:
            data["generation_energy"] = {}
            data["generation"] = {}
            return

        generation = await get_power_payload(
            self.hass,
            self.power_sensor,
            start_time=dt_util.start_of_local_day(),
        )
        data["generation"] = generation
        data["generation_energy"] = power_to_energy(generation)
