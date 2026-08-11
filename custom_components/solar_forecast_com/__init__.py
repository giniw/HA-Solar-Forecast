"""The Solar Forecast integration."""

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from pathlib import Path
import logging

from .panel import async_register_panel
from .views import SolarForecastView, SolarForecastEntitiesView, SolarForecastEntriesView
from .const import DOMAIN, CONF_API_KEY
from .coordinator import ForecastCoordinator
from homeassistant.helpers import entity_registry as er


PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Set up the integration from configuration.yaml."""

    path = Path(__file__).parent / "frontend"

    await hass.http.async_register_static_paths([
        StaticPathConfig("/solar_forecast", str(path), False)
       ])

    hass.http.register_view(SolarForecastView())

    hass.http.register_view(SolarForecastEntitiesView())

    hass.http.register_view( SolarForecastEntriesView())
    await async_register_panel(hass)

    return True


async def async_setup_entry(hass, entry: ConfigEntry):
    """Set up Solar Forecast from a config entry."""

    coordinator = ForecastCoordinator(
        hass,
        entry.data[CONF_API_KEY],
        entry,
    )

    # Fetch initial data
    try:
        await coordinator.async_config_entry_first_refresh()

#        _LOGGER.warning("Response %s: %s", entry.entry_id, coordinator.data)
    except Exception as e:
        _LOGGER.warning("Error: %s", e)

    

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    _LOGGER.warning(
        "Coordinator %s update_interval=%s",
        id(coordinator),
        coordinator.update_interval,
     )

    _LOGGER.warning(
        "Coordinator internals: %s",
        [k for k in coordinator.__dict__.keys() if "refresh" in k or "unsub" in k]
     )
    
    _LOGGER.warning(
        "_unsub_refresh = %s",
        coordinator._unsub_refresh,
    )

    _LOGGER.warning("Response %s: %s", entry.entry_id ,hass.data[DOMAIN].get(entry.entry_id).data)

    # Load platforms
    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )
#    path = Path(__file__).parent / "frontend"
#
#    await hass.http.async_register_static_paths([
#    StaticPathConfig("/solar_forecast", str(path), False)
#       ])

#    _LOGGER.warning("About to register view")


#    hass.http.register_view(
#        SolarForecastView()
#    )
#    hass.http.register_view(
#        SolarForecastEntitiesView()
#    )
#    hass.http.register_view(
#        SolarForecastEntriesView()
#    )

#    _LOGGER.warning("View registered")

#    if not hass.data.get(f"{DOMAIN}_panel_registered"):
#        hass.http.register_view(SolarForecastView())
#
#        hass.http.register_view(SolarForecastEntitiesView())

#        hass.http.register_view( SolarForecastEntriesView())

#        await async_register_panel(hass)

#        _LOGGER.warning("View registered")

#    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)



    return True

async def async_delete_statistics(
    hass: HomeAssistant,
    entry,
):
    """Delete recorder history/statistics for all entities."""

    entity_ids = _get_entity_ids(hass, entry.entry_id)

    if not entity_ids:
        return

    await hass.services.async_call(
        "recorder",
        "purge_entities",
        {
            "entity_id": entity_ids,
            "keep_days": 0,
            "repack": False,
        },
        blocking=True,
    )


def _get_entity_ids(hass, entry_id):
    """Return all entity IDs belonging to a config entry."""

    registry = er.async_get(hass)

    return [
        entity.entity_id
        for entity in registry.entities.values()
        if entity.config_entry_id == entry_id
    ]



async def async_unload_entry(hass, entry: ConfigEntry):
    """Unload a config entry."""
    _LOGGER.warning("UNLOADING %s", entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )
    await async_delete_statistics(hass, entry)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    registry = er.async_get(hass)


    for entity_id in _get_entity_ids(hass, entry.entry_id):
        registry.async_remove(entity_id)


    return unload_ok



async def async_remove_entry(hass, entry):

    await async_delete_statistics(hass, entry)

    return True
