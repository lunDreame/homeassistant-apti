"""The APT.i component."""

from __future__ import annotations

from datetime import datetime
import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.components import persistent_notification
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.helpers.config_validation as cv

from .coordinator import APTiDataUpdateCoordinator
from .const import (
    DOMAIN,
    PLATFORMS,
    UPDATE_SESSION_INTERVAL,
    UPDATE_MAINT_INTERVAL,
    UPDATE_ENERGY_INTERVAL
)

format_date = datetime.now().strftime("%Y%m%d")

VISIT_RESERVATION_SCHEMA = vol.Schema({
    vol.Required("car_no"): cv.string,
    vol.Required("phone_no"): cv.string,
    vol.Required("visit_date", default=format_date): cv.datetime,
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the APT.i integration."""
    coordinator = APTiDataUpdateCoordinator(hass, entry)

    await coordinator.api.login()
    await coordinator.async_config_entry_first_refresh()
    
    async_track_time_interval(
        hass, coordinator.api.login, UPDATE_SESSION_INTERVAL,
        cancel_on_shutdown=True
    )
    async_track_time_interval(
        hass, coordinator._update_maint, UPDATE_MAINT_INTERVAL,
        cancel_on_shutdown=True
    )
    async_track_time_interval(
        hass, coordinator._update_energy, UPDATE_ENERGY_INTERVAL,
        cancel_on_shutdown=True
    )

    entry.runtime_data = coordinator

    #await _async_setup_service(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the APT.i integration."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    ):
        coordinator: APTiDataUpdateCoordinator = entry.runtime_data
    return unload_ok


async def _async_setup_service(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up the service."""

    async def _async_visit_reservation(call: ServiceCall) -> ServiceResponse:
        """Perform vehicle visit reservation service."""
