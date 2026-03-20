"""Binary sensors for APTi."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import APTiDataUpdateCoordinator
from .entity import (
    AptiCoordinatorEntity,
    DEVICE_ACCOUNT,
    DEVICE_MANAGEMENT_FEE,
    DEVICE_PARKING,
)


def _yn_to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if text in {"Y", "YES", "TRUE", "1"}:
        return True
    if text in {"N", "NO", "FALSE", "0"}:
        return False
    return None


@dataclass(slots=True)
class AptiBinarySensorDescription:
    """Definition for binary sensor."""

    key: str
    name: str
    value_fn: Callable[[dict[str, Any]], bool | None]
    icon: str | None = None
    device_key: str = DEVICE_ACCOUNT


DESCRIPTIONS: tuple[AptiBinarySensorDescription, ...] = (
    AptiBinarySensorDescription(
        key="mgmt_payment_completed",
        name="관리비 납부완료",
        icon="mdi:check-decagram",
        device_key=DEVICE_MANAGEMENT_FEE,
        value_fn=lambda d: bool(d.get("management_fee", {}).get("paymentCompleted")),
    ),
    AptiBinarySensorDescription(
        key="mgmt_auto_transfer",
        name="관리비 자동이체",
        icon="mdi:bank-check",
        device_key=DEVICE_MANAGEMENT_FEE,
        value_fn=lambda d: _yn_to_bool(d.get("manage_home", {}).get("autoTransferYN")),
    ),
    AptiBinarySensorDescription(
        key="electronic_bill",
        name="전자고지",
        icon="mdi:email-fast",
        device_key=DEVICE_ACCOUNT,
        value_fn=lambda d: _yn_to_bool(d.get("account", {}).get("electronicBill")),
    ),
    AptiBinarySensorDescription(
        key="parking_service_enabled",
        name="주차 서비스 사용가능",
        icon="mdi:car-connected",
        device_key=DEVICE_PARKING,
        value_fn=lambda d: bool(d.get("parking_visit", {}).get("serviceYn")),
    ),
    AptiBinarySensorDescription(
        key="parking_reservation_enabled",
        name="주차 예약제 운영",
        icon="mdi:calendar-clock",
        device_key=DEVICE_PARKING,
        value_fn=lambda d: bool(d.get("parking_visit", {}).get("isReservation")),
    ),
    AptiBinarySensorDescription(
        key="parking_is_reservable",
        name="주차 예약 가능",
        icon="mdi:car-key",
        device_key=DEVICE_PARKING,
        value_fn=lambda d: bool(d.get("parking_visit", {}).get("isReservable")),
    ),
    AptiBinarySensorDescription(
        key="parking_holiday_exception",
        name="공휴일 예외 적용",
        icon="mdi:calendar-alert",
        device_key=DEVICE_PARKING,
        value_fn=lambda d: _yn_to_bool(
            d.get("parking_visit", {}).get("exceptions", {}).get("exHolidayUseYn")
        ),
    ),
    AptiBinarySensorDescription(
        key="parking_saturday_exception",
        name="토요일 예외 적용",
        icon="mdi:calendar-weekend",
        device_key=DEVICE_PARKING,
        value_fn=lambda d: _yn_to_bool(
            d.get("parking_visit", {}).get("exceptions", {}).get("exSatUseYn")
        ),
    ),
    AptiBinarySensorDescription(
        key="parking_sunday_exception",
        name="일요일 예외 적용",
        icon="mdi:calendar-weekend-outline",
        device_key=DEVICE_PARKING,
        value_fn=lambda d: _yn_to_bool(
            d.get("parking_visit", {}).get("exceptions", {}).get("exSunUseYn")
        ),
    ),
    AptiBinarySensorDescription(
        key="parking_operating_apt",
        name="주차 서비스 운영 단지",
        icon="mdi:office-building-check",
        device_key=DEVICE_PARKING,
        value_fn=lambda d: _yn_to_bool(
            d.get("parking_application_status", {}).get("isInOperationApt")
        ),
    ),
    AptiBinarySensorDescription(
        key="parking_applied",
        name="주차 서비스 신청 완료",
        icon="mdi:clipboard-check",
        device_key=DEVICE_PARKING,
        value_fn=lambda d: _yn_to_bool(d.get("parking_application_status", {}).get("isApplied")),
    ),
    AptiBinarySensorDescription(
        key="parking_active",
        name="방문차량 주차중",
        icon="mdi:car",
        device_key=DEVICE_PARKING,
        value_fn=lambda d: (d.get("parking_visit", {}).get("parkedTime") or 0) > 0,
    ),
)


class AptiBinarySensor(AptiCoordinatorEntity, BinarySensorEntity):
    """Simple binary sensor wrapper."""

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: AptiBinarySensorDescription,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            f"binary_{description.key}",
            device_key=description.device_key,
        )
        self.entity_description = description
        self._attr_name = description.name
        self._attr_icon = description.icon

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up APTi binary sensors."""
    coordinator: APTiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities(
        AptiBinarySensor(coordinator, config_entry, description) for description in DESCRIPTIONS
    )
