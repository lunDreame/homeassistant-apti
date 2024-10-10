"""Base class for APT.i entities."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.entity import Entity, DeviceInfo
from homeassistant.core import callback

from .coordinator import APTiDataUpdateCoordinator
from .const import DOMAIN


class APTiBase:
    """Base class for APT.i."""

    def __init__(
        self, coordinator: APTiDataUpdateCoordinator, description
    ):
        self.coordinator = coordinator
        self.description = description
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        return DeviceInfo(
            configuration_url="https://www.apti.co.kr/apti/",
            identifiers={(
                DOMAIN, f"{self.coordinator.id}_{self.description.chepter_name}"
            )},
            manufacturer="APT.i Co.,Ltd.",
            model="APT.i",
            name=self.description.chepter_name,
        )


class APTiDevice(APTiBase, Entity):
    """APT.i device class."""

    def __init__(self, coordinator, description):
        super().__init__(coordinator, description)
        self._attr_has_entity_name = True

    @property
    def entity_registry_enabled_default(self):
        """Return whether the entity registry is enabled."""
        return True

    async def async_added_to_hass(self):
        """Called when added to Hass."""
        self.coordinator.api.data.add_callback(self.async_update_callback)
        self.schedule_update_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Called when removed from Hass."""
        self.coordinator.api.data.remove_callback(self.async_update_callback)

    @callback
    def async_restore_last_state(self, last_state) -> None:
        """Restore the last state."""
        pass

    @callback
    def async_update_callback(self):
        """Schedule a state update callback."""
        self.async_schedule_update_ha_state()

    @property
    def available(self) -> bool:
        """Return whether the device is available."""
        return self.coordinator.api.logged_in

    @property
    def should_poll(self) -> bool:
        """Return whether polling is needed."""
        return True
