from datetime import timedelta
import logging

from aiohttp import ClientError

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .arrays import normalize_arrays
from .const import API_URL, API_URL_GENERATION, DOMAIN
from .energy import energy_to_power

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

            return data

        except ClientError as err:
            raise UpdateFailed(err) from err
