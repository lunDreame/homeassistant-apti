"""Shared entity helpers for APTi."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import APTiDataUpdateCoordinator

_RE_NON_WORD = re.compile(r"[^0-9a-zA-Z_]+")


def slugify(value: str) -> str:
    """Return stable slug text from free-form string."""
    cleaned = _RE_NON_WORD.sub("_", value.strip())
    cleaned = cleaned.strip("_").lower()
    return cleaned or "unknown"


class AptiCoordinatorEntity(CoordinatorEntity[APTiDataUpdateCoordinator]):
    """Base entity class using a shared device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        unique_suffix: str,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_{unique_suffix}"

    @property
    def device_info(self) -> DeviceInfo:
        """Expose a single apartment device for all entities."""
        account = self.coordinator.data.get("account", {})
        apt_name = str(account.get("aptName") or account.get("apt_name") or NAME).strip()
        dong = str(account.get("dong") or account.get("aptDong") or "").strip()
        ho = str(account.get("ho") or account.get("aptHo") or "").strip()

        label = apt_name
        if dong and ho:
            label = f"{apt_name} {dong}-{ho}"

        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            manufacturer=MANUFACTURER,
            model="Apartment",
            name=label,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return common attributes."""
        account = self.coordinator.data.get("account", {})
        attrs: dict[str, Any] = {
            "apti_user_id": account.get("userId"),
            "apt_code": account.get("code"),
        }
        return attrs

