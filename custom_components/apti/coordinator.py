"""DataUpdateCoordinator for the APT.i."""

from __future__ import annotations
import asyncio

from datetime import datetime
from typing import Any

from homeassistant.const import CONF_ID, CONF_PASSWORD
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
        self.id = entry.data.get(CONF_ID)
        self.password = entry.data.get(CONF_PASSWORD)
        self.api = APTiAPI(hass, entry, self.id, self.password)
        self.entities: dict[str, dict | list] = dict()

    async def _update_maint_energy(self, _=None):
        """Fetch maintenance/energy data from the API."""
        if isinstance(_, datetime):
            LOGGER.info("Update maintenance/energy data.")
            await self.api.login()
        await asyncio.gather(
            self.api.get_maint_fee_item(),
            self.api.get_maint_fee_payment(),
            self.api.get_energy_category(),
            self.api.get_energy_type()
        )
        self.api.data.update_callback()

    def data_to_entities(self) -> dict[str, dict | list]:
        """Convert APT.i data to entities."""
        data_items = {
            "maint_item": self.api.data.maint.item,
            "maint_payment": self.api.data.maint.payment_amount,
            "energy_usage": self.api.data.energy.item_usage,
            "energy_detail": self.api.data.energy.detail_usage,
            "energy_type": self.api.data.energy.type_usage,
        }
        for entity_key, value in data_items.items():
            self.entities[entity_key] = value
        return self.entities

    async def _async_update_data(self) -> dict[str, dict | list]:
        """Update APT.i devices data."""
        try:
            await self._update_maint_energy()
            return self.data_to_entities()
        except Exception as ex:
            raise UpdateFailed(f"Failed to update APT.i data: {ex}") from ex
