"""DataUpdateCoordinator for the APT.i."""

from __future__ import annotations
import asyncio

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .apti import APTiAPI
from .const import DOMAIN, LOGGER


class APTiDataUpdateCoordinator(DataUpdateCoordinator):
    """APT.i Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize data coordinator."""
        super().__init__(hass, LOGGER, name=DOMAIN)
        self.hass = hass
        self.entry = entry
        self.api = APTiAPI(hass, entry)
        self.entities: dict[str, dict | list] = dict()

    async def _update_maint(self, _=None):
        """Fetch maintenance data from the API."""
        await self.api.get_maint_fee_payment()
        await self.api.get_maint_fee_item()
        self.api.data.update_callback()
        self.api.data.maint.update_time = datetime.now()

    async def _update_energy(self, _=None):
        """Fetch energy data from the API."""
        await asyncio.gather(
            self.api.get_energy_category(),
            self.api.get_energy_type()
        )
        self.api.data.update_callback()
        self.api.data.energy.update_time = datetime.now()

    def data_to_entities(self) -> dict[str, dict | list]:
        """Convert APT.i data to entities."""
        data_items = {
            "maint_payment": self.api.data.maint.payment,
            "maint_cost": self.api.data.maint.cost,
            "maint_update_time": self.api.data.maint.update_time,
            "energy_usage": self.api.data.energy.usage,
            "energy_detail": self.api.data.energy.detail,
            "energy_type": self.api.data.energy.type,
            "energy_update_time": self.api.data.energy.update_time
        }
        for entity_key, value in data_items.items():
            self.entities[entity_key] = value
        return self.entities

    async def _async_update_data(self) -> dict[str, dict | list]:
        """Update APT.i devices data."""
        try:
            await self._update_maint()
            await self._update_energy()
            return self.data_to_entities()
        except Exception as ex:
            raise UpdateFailed(f"Failed to update APT.i data: {ex}") from ex
