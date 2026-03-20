"""Shared entity helpers for APTi."""

from __future__ import annotations

from dataclasses import dataclass
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import APTiDataUpdateCoordinator

_RE_NON_WORD = re.compile(r"[^0-9a-zA-Z_]+")

DEVICE_ACCOUNT = "account"
DEVICE_MANAGEMENT_FEE = "management_fee"
DEVICE_PARKING = "parking"
DEVICE_PAYMENT = "payment"
DEVICE_ENERGY = "energy"
DEVICE_SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class AptiDeviceDescriptor:
    """Device metadata for category grouping."""

    name: str
    model: str


DEVICE_DESCRIPTORS: dict[str, AptiDeviceDescriptor] = {
    DEVICE_ACCOUNT: AptiDeviceDescriptor(name="계정", model="Account"),
    DEVICE_MANAGEMENT_FEE: AptiDeviceDescriptor(name="관리비", model="Management Fee"),
    DEVICE_PARKING: AptiDeviceDescriptor(name="주차", model="Parking"),
    DEVICE_PAYMENT: AptiDeviceDescriptor(name="납부", model="Payment"),
    DEVICE_ENERGY: AptiDeviceDescriptor(name="에너지", model="Energy"),
    DEVICE_SYSTEM: AptiDeviceDescriptor(name="시스템", model="System"),
}


def slugify(value: str) -> str:
    """Return stable slug text from free-form string."""
    cleaned = _RE_NON_WORD.sub("_", value.strip())
    cleaned = cleaned.strip("_").lower()
    return cleaned or "unknown"


class AptiCoordinatorEntity(CoordinatorEntity[APTiDataUpdateCoordinator]):
    """Base entity class grouped by category devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        unique_suffix: str,
        device_key: str,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._device_key = (
            device_key if device_key in DEVICE_DESCRIPTORS else DEVICE_SYSTEM
        )
        self._attr_unique_id = f"{config_entry.entry_id}_{self._device_key}_{unique_suffix}"

    @property
    def device_info(self) -> DeviceInfo:
        """Expose category-specific devices for readability."""
        account = self.coordinator.data.get("account", {})
        apt_name = str(account.get("aptName") or account.get("apt_name") or NAME).strip()
        dong = str(account.get("dong") or account.get("aptDong") or "").strip()
        ho = str(account.get("ho") or account.get("aptHo") or "").strip()

        label = apt_name or NAME
        if dong and ho:
            label = f"{apt_name} {dong}-{ho}"

        descriptor = DEVICE_DESCRIPTORS[self._device_key]

        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._config_entry.entry_id}_{self._device_key}")},
            manufacturer=MANUFACTURER,
            model=descriptor.model,
            name=f"{label} {descriptor.name}",
        )
