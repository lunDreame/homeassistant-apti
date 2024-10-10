"""The APT.i component."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_interval

from .coordinator import APTiDataUpdateCoordinator
from .const import PLATFORMS, UPDATE_ME_INTERVAL


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the APT.i integration."""
    coordinator = APTiDataUpdateCoordinator(hass, entry)

    await coordinator.api.login()
    await coordinator.async_config_entry_first_refresh()
    
    async_track_time_interval(
        hass, coordinator._update_maint_energy, UPDATE_ME_INTERVAL,
        cancel_on_shutdown=True
    )

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the APT.i integration."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    ):
        coordinator: APTiDataUpdateCoordinator = entry.runtime_data
    
    return unload_ok
