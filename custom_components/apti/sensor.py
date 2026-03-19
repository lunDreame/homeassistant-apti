"""Sensor platform for APTi."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    CURRENCY_KRW,
    PERCENTAGE,
    UnitOfArea,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_SCAN_INTERVAL_MINUTES, DOMAIN, PAYMENT_STATE_CODES
from .coordinator import APTiDataUpdateCoordinator
from .entity import AptiCoordinatorEntity, slugify


def _parse_yyyymmdd(value: str | None) -> date | None:
    if not value or len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _get_latest_payment_row(data: dict[str, Any]) -> dict[str, Any] | None:
    histories = data.get("payment_histories", {})
    rows = histories.get("001", []) if isinstance(histories, dict) else []
    if not isinstance(rows, list) or not rows:
        return None
    candidates = [row for row in rows if isinstance(row, dict)]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: (
            str(row.get("payDate", "")),
            str(row.get("billYm", "")),
        ),
    )


@dataclass(slots=True)
class AptiSensorDescription:
    """Definition for simple static sensors."""

    key: str
    name: str
    value_fn: Callable[[dict[str, Any]], Any]
    native_unit_of_measurement: str | None = None
    device_class: SensorDeviceClass | None = None
    icon: str | None = None
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


STATIC_SENSORS: tuple[AptiSensorDescription, ...] = (
    AptiSensorDescription(
        key="mgmt_month_fee",
        name="당월 관리비",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda d: _safe_int(d.get("manage_home", {}).get("monthFee")),
    ),
    AptiSensorDescription(
        key="mgmt_previous_month_fee",
        name="전월 관리비",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda d: _safe_int(d.get("manage_home", {}).get("bfMonthFee")),
    ),
    AptiSensorDescription(
        key="mgmt_due_fee",
        name="납부 대상 금액",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda d: _safe_int(d.get("manage_home", {}).get("bfDueFee")),
    ),
    AptiSensorDescription(
        key="mgmt_discount_total",
        name="총 할인 금액",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda d: _safe_int(
            d.get("management_fee", {}).get("discount", {}).get("discountFee")
        ),
    ),
    AptiSensorDescription(
        key="mgmt_bill_month",
        name="청구월",
        icon="mdi:calendar-month",
        value_fn=lambda d: d.get("manage_home", {}).get("billYm"),
    ),
    AptiSensorDescription(
        key="mgmt_due_date",
        name="관리비 마감일",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda d: _parse_yyyymmdd(
            (
                d.get("manage_home", {})
                .get("paymentInformation", [{}])[0]
                .get("endDate")
            )
            if d.get("manage_home", {}).get("paymentInformation")
            else None
        ),
    ),
    AptiSensorDescription(
        key="mgmt_area",
        name="전용면적",
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        value_fn=lambda d: _safe_float(d.get("manage_home", {}).get("area")),
    ),
    AptiSensorDescription(
        key="energy_my_fee",
        name="에너지 요금(우리집)",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda d: _safe_int(
            d.get("manage_home", {}).get("energyCondition", {}).get("myFee")
        ),
    ),
    AptiSensorDescription(
        key="energy_avg_fee",
        name="에너지 요금(평균)",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda d: _safe_int(
            d.get("manage_home", {}).get("energyCondition", {}).get("avgFee")
        ),
    ),
    AptiSensorDescription(
        key="energy_compared_avg",
        name="평균 대비 에너지 사용",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: _safe_int(
            d.get("manage_home", {}).get("energyCondition", {}).get("compAvg")
        ),
    ),
    AptiSensorDescription(
        key="parking_parked_minutes",
        name="누적 주차시간",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:car-clock",
        value_fn=lambda d: _safe_int(d.get("parking_visit", {}).get("parkedTime")),
    ),
    AptiSensorDescription(
        key="parking_remaining_minutes",
        name="무료 잔여시간",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-sand",
        value_fn=lambda d: _safe_int(d.get("parking_visit", {}).get("remainTime")),
    ),
    AptiSensorDescription(
        key="parking_expected_fee",
        name="예상 주차요금",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda d: _safe_int(d.get("parking_visit", {}).get("expectedParkingFee")),
    ),
    AptiSensorDescription(
        key="parking_based_minutes",
        name="주차 기본시간",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:clock-outline",
        value_fn=lambda d: _safe_int(d.get("parking_visit", {}).get("basedMinutes")),
    ),
    AptiSensorDescription(
        key="parking_based_minutes_fare",
        name="주차 기본단가",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda d: _safe_int(d.get("parking_visit", {}).get("basedMinutesFare")),
    ),
    AptiSensorDescription(
        key="parking_visit_vehicle_count",
        name="방문차량 건수",
        icon="mdi:car-multiple",
        value_fn=lambda d: len(d.get("parking_visit", {}).get("carListResDtoList", [])),
    ),
    AptiSensorDescription(
        key="payment_history_latest_bill_month",
        name="최근 납부월",
        icon="mdi:calendar-check",
        value_fn=lambda d: (_get_latest_payment_row(d) or {}).get("billYm"),
    ),
    AptiSensorDescription(
        key="payment_history_latest_paid_date",
        name="최근 납부일",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda d: _parse_yyyymmdd((_get_latest_payment_row(d) or {}).get("payDate")),
    ),
    AptiSensorDescription(
        key="payment_history_latest_paid_amount",
        name="최근 납부금액",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda d: _safe_int((_get_latest_payment_row(d) or {}).get("amt")),
    ),
    AptiSensorDescription(
        key="payment_next_bill_month",
        name="다음 청구월",
        icon="mdi:calendar-arrow-right",
        value_fn=lambda d: d.get("manage_payment_next", {}).get("nextBillYm"),
    ),
    AptiSensorDescription(
        key="payment_my_cash",
        name="보유 캐시",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda d: _safe_int(d.get("manage_payment_next", {}).get("myCash")),
    ),
    AptiSensorDescription(
        key="payment_coupon_count",
        name="보유 쿠폰수",
        icon="mdi:ticket-percent",
        value_fn=lambda d: _safe_int(d.get("manage_payment_next", {}).get("couponCnt")),
    ),
    AptiSensorDescription(
        key="autodiscount_honey",
        name="꿀단지 할인 사용",
        icon="mdi:honey-outline",
        value_fn=lambda d: d.get("manage_auto_discount", {}).get("honeyYn"),
    ),
    AptiSensorDescription(
        key="autodiscount_schedule_month",
        name="자동할인 예정월",
        icon="mdi:calendar-star",
        value_fn=lambda d: d.get("manage_auto_discount", {}).get("schBillYm"),
    ),
    AptiSensorDescription(
        key="refresh_interval_minutes",
        name="갱신 주기",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:update",
        value_fn=lambda d: _safe_int(d.get("_scan_interval")),
    ),
)


class AptiStaticSensor(AptiCoordinatorEntity, SensorEntity):
    """Static sensor whose value comes from a function."""

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        description: AptiSensorDescription,
    ) -> None:
        super().__init__(coordinator, config_entry, f"sensor_{description.key}")
        self.entity_description = description
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_device_class = description.device_class

    @property
    def native_value(self) -> Any:
        data = dict(self.coordinator.data)
        data["_scan_interval"] = self._config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
        )
        return self.entity_description.value_fn(data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attrs = super().extra_state_attributes or {}
        if self.entity_description.attrs_fn:
            attrs.update(self.entity_description.attrs_fn(self.coordinator.data))
        return attrs


class AptiManagementDetailFeeSensor(AptiCoordinatorEntity, SensorEntity):
    """Per-item management fee sensor."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY_KRW
    _attr_icon = "mdi:cash-multiple"

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        item_no: str,
        item_name: str,
    ) -> None:
        super().__init__(coordinator, config_entry, f"detail_fee_{item_no}_{slugify(item_name)}")
        self._item_no = item_no
        self._item_name = item_name
        self._attr_name = f"관리비 {item_name}"

    def _get_item(self) -> dict[str, Any] | None:
        detail = self.coordinator.data.get("management_fee", {}).get("detail", [])
        if not isinstance(detail, list):
            return None
        for item in detail:
            if isinstance(item, dict) and str(item.get("itemNo")) == self._item_no:
                return item
        return None

    @property
    def native_value(self) -> int | None:
        item = self._get_item()
        return _safe_int(item.get("fee")) if item else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attrs = super().extra_state_attributes or {}
        item = self._get_item()
        if not item:
            return attrs

        attrs.update(
            {
                "item_no": item.get("itemNo"),
                "item_name": item.get("itemName"),
                "increase": item.get("increase"),
                "usage": item.get("usage"),
                "unit": item.get("unit"),
                "sub_items": item.get("list") or [],
            }
        )
        return attrs


class AptiDiscountSensor(AptiCoordinatorEntity, SensorEntity):
    """Discount amount sensor from maintenance/energy sections."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY_KRW
    _attr_icon = "mdi:tag"

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        discount_group: str,
        title: str,
        sub_title: str | None = None,
    ) -> None:
        unique = f"discount_{slugify(discount_group)}_{slugify(title)}"
        if sub_title:
            unique = f"{unique}_{slugify(sub_title)}"
        super().__init__(coordinator, config_entry, unique)
        self._group = discount_group
        self._title = title
        self._sub_title = sub_title

        if sub_title:
            self._attr_name = f"할인 {title} {sub_title}"
        else:
            self._attr_name = f"할인 {title}"

    def _find_amount(self) -> int | None:
        discount = self.coordinator.data.get("management_fee", {}).get("discount", {})
        if not isinstance(discount, dict):
            return None

        entries = discount.get(self._group, [])
        if not isinstance(entries, list):
            return None

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("title")) != self._title:
                continue
            if not self._sub_title:
                return _safe_int(entry.get("amt"))

            children = entry.get("data", [])
            if not isinstance(children, list):
                return None
            for child in children:
                if not isinstance(child, dict):
                    continue
                if str(child.get("title")) == self._sub_title:
                    return _safe_int(child.get("amt"))
            return None
        return None

    @property
    def native_value(self) -> int | None:
        return self._find_amount()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attrs = super().extra_state_attributes or {}
        attrs.update({"group": self._group, "title": self._title, "sub_title": self._sub_title})
        return attrs


class AptiPaymentStateSensor(AptiCoordinatorEntity, SensorEntity):
    """Count/total sensors per payment history state code."""

    _attr_icon = "mdi:history"

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        state_code: str,
        mode: str,
    ) -> None:
        super().__init__(coordinator, config_entry, f"payment_state_{state_code}_{mode}")
        self._state_code = state_code
        self._mode = mode
        if mode == "count":
            self._attr_name = f"납부이력 {state_code} 건수"
            self._attr_icon = "mdi:counter"
        else:
            self._attr_name = f"납부이력 {state_code} 금액"
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_native_unit_of_measurement = CURRENCY_KRW

    def _rows(self) -> list[dict[str, Any]]:
        rows = self.coordinator.data.get("payment_histories", {}).get(self._state_code, [])
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    @property
    def native_value(self) -> int:
        rows = self._rows()
        if self._mode == "count":
            return len(rows)
        return sum(_safe_int(row.get("amt")) or 0 for row in rows)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attrs = super().extra_state_attributes or {}
        rows = self._rows()
        latest = (
            max(
                rows,
                key=lambda row: (
                    str(row.get("payDate", "")),
                    str(row.get("billYm", "")),
                ),
            )
            if rows
            else None
        )
        attrs.update(
            {
                "state_code": self._state_code,
                "state_name": latest.get("stateName") if latest else None,
                "latest_bill_month": latest.get("billYm") if latest else None,
                "latest_paid_date": latest.get("payDate") if latest else None,
            }
        )
        return attrs


class AptiParkingRecentVisitSensor(AptiCoordinatorEntity, SensorEntity):
    """Expose recent visit vehicle list as attributes."""

    _attr_icon = "mdi:car-info"
    _attr_name = "방문차량 상세"

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, config_entry, "parking_recent_visits")

    def _cars(self) -> list[dict[str, Any]]:
        cars = self.coordinator.data.get("parking_visit", {}).get("carListResDtoList", [])
        if not isinstance(cars, list):
            return []
        return [car for car in cars if isinstance(car, dict)]

    @property
    def native_value(self) -> int:
        return len(self._cars())

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attrs = super().extra_state_attributes or {}
        cars = self._cars()
        attrs["cars"] = [
            {
                "car_no": car.get("carNoInformation"),
                "visit_date": car.get("visitDate"),
                "in_date": car.get("carInDate"),
                "out_date": car.get("carOutDate"),
                "parked_minutes": car.get("parkedTimeLong") or car.get("parkedTime"),
                "discount_minutes": car.get("discountTime"),
                "calc_minutes": car.get("calcTime"),
                "visit_type": car.get("visitType"),
            }
            for car in cars
        ]
        return attrs


class AptiEnergySensor(AptiCoordinatorEntity, SensorEntity):
    """Fee/usage sensor for a single energy category."""

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        energy_key: str,
        metric: str,
    ) -> None:
        super().__init__(coordinator, config_entry, f"energy_{energy_key}_{metric}")
        self._energy_key = energy_key
        self._metric = metric
        labels = {
            "electric": "전기",
            "water": "수도",
            "heat": "난방",
            "hotwater": "급탕",
        }
        metric_label = "요금" if metric == "fee" else "사용량"
        self._attr_name = f"{labels.get(energy_key, energy_key)} {metric_label}"
        if metric == "fee":
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_native_unit_of_measurement = CURRENCY_KRW
            self._attr_icon = "mdi:cash"
        else:
            self._attr_icon = "mdi:gauge"

    def _energy_obj(self) -> dict[str, Any] | None:
        energy = self.coordinator.data.get("manage_energy", {}).get("energy", {})
        if not isinstance(energy, dict):
            return None
        item = energy.get(self._energy_key, {})
        if not isinstance(item, dict):
            return None
        return item

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self._metric == "fee":
            return self._attr_native_unit_of_measurement
        item = self._energy_obj()
        if not item:
            return None
        return item.get("unit")

    @property
    def native_value(self) -> int | float | None:
        item = self._energy_obj()
        if not item:
            return None
        value = item.get(self._metric)
        if self._metric == "fee":
            return _safe_int(value)
        return _safe_float(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attrs = super().extra_state_attributes or {}
        item = self._energy_obj()
        if item:
            attrs.update({"energy_key": self._energy_key, "unit": item.get("unit")})
        return attrs


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up APTi sensors."""
    coordinator: APTiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    entities: list[SensorEntity] = []

    entities.extend(
        AptiStaticSensor(coordinator, config_entry, description) for description in STATIC_SENSORS
    )

    for state_code in PAYMENT_STATE_CODES:
        entities.append(AptiPaymentStateSensor(coordinator, config_entry, state_code, "count"))
        entities.append(AptiPaymentStateSensor(coordinator, config_entry, state_code, "amount"))

    for energy_key in ("electric", "water", "heat", "hotwater"):
        entities.append(AptiEnergySensor(coordinator, config_entry, energy_key, "fee"))
        entities.append(AptiEnergySensor(coordinator, config_entry, energy_key, "use"))

    detail_items = coordinator.data.get("management_fee", {}).get("detail", [])
    if isinstance(detail_items, list):
        for item in detail_items:
            if not isinstance(item, dict):
                continue
            item_no = str(item.get("itemNo") or "").strip()
            item_name = str(item.get("itemName") or "").strip()
            if not item_no or not item_name:
                continue
            entities.append(
                AptiManagementDetailFeeSensor(coordinator, config_entry, item_no, item_name)
            )

    discount = coordinator.data.get("management_fee", {}).get("discount", {})
    if isinstance(discount, dict):
        maintenance = discount.get("maintenance", [])
        if isinstance(maintenance, list):
            for row in maintenance:
                if isinstance(row, dict) and row.get("title"):
                    entities.append(
                        AptiDiscountSensor(
                            coordinator,
                            config_entry,
                            "maintenance",
                            str(row["title"]),
                        )
                    )

        energy_discounts = discount.get("energy", [])
        if isinstance(energy_discounts, list):
            for row in energy_discounts:
                if not isinstance(row, dict) or not row.get("title"):
                    continue
                title = str(row["title"])
                entities.append(AptiDiscountSensor(coordinator, config_entry, "energy", title))
                for child in row.get("data", []) or []:
                    if isinstance(child, dict) and child.get("title"):
                        entities.append(
                            AptiDiscountSensor(
                                coordinator,
                                config_entry,
                                "energy",
                                title,
                                str(child["title"]),
                            )
                        )

    entities.append(AptiParkingRecentVisitSensor(coordinator, config_entry))
    async_add_entities(entities)
