"""Sensor platform for APTi."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    PERCENTAGE,
    UnitOfArea,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_SCAN_INTERVAL_MINUTES, DOMAIN, PAYMENT_STATE_CODES
from .coordinator import APTiDataUpdateCoordinator
from .entity import (
    AptiCoordinatorEntity,
    DEVICE_ACCOUNT,
    DEVICE_ENERGY,
    DEVICE_MANAGEMENT_FEE,
    DEVICE_PARKING,
    DEVICE_PAYMENT,
    DEVICE_SYSTEM,
    slugify,
)

CURRENCY_KRW = "KRW"


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
    normalized = str(value).replace(",", "")
    try:
        return float(normalized)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    normalized = str(value).replace(",", "")
    try:
        return int(float(normalized))
    except (TypeError, ValueError):
        return None


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


def _management_detail_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    detail = data.get("management_fee", {}).get("detail", [])
    if not isinstance(detail, list):
        return []
    return [item for item in detail if isinstance(item, dict)]


def _find_management_detail_item(data: dict[str, Any], item_no: str) -> dict[str, Any] | None:
    for item in _management_detail_rows(data):
        if str(item.get("itemNo") or "") == item_no:
            return item
    return None


def _parking_visit_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    cars = data.get("parking_visit", {}).get("carListResDtoList", [])
    if not isinstance(cars, list):
        return []
    return [car for car in cars if isinstance(car, dict)]


def _pick_dynamic_value_key(payload: dict[str, Any], preferred: tuple[str, ...]) -> str | None:
    for key in preferred:
        if payload.get(key) is not None:
            return key

    for key, value in payload.items():
        if key in {"title", "itemName", "name"}:
            continue
        if isinstance(value, (str, int, float)) and value not in ("", None):
            return key
    return None


def _pick_scalar_value(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if payload.get(key) is not None:
            return payload.get(key)
    return None


@dataclass(slots=True)
class AptiSensorDescription:
    """Definition for simple static sensors."""

    key: str
    name: str
    value_fn: Callable[[dict[str, Any]], Any]
    native_unit_of_measurement: str | None = None
    device_class: SensorDeviceClass | None = None
    icon: str | None = None
    device_key: str = DEVICE_SYSTEM


@dataclass(frozen=True, slots=True)
class AptiParkingVisitFieldDescription:
    """Definition for parking visit detail sensor."""

    key: str
    name: str
    source_keys: tuple[str, ...]
    icon: str | None = None
    native_unit_of_measurement: str | None = None
    device_class: SensorDeviceClass | None = None


PARKING_VISIT_FIELDS: tuple[AptiParkingVisitFieldDescription, ...] = (
    AptiParkingVisitFieldDescription(
        key="car_no",
        name="차량번호",
        source_keys=("carNoInformation",),
        icon="mdi:car-info",
    ),
    AptiParkingVisitFieldDescription(
        key="visit_date",
        name="방문일",
        source_keys=("visitDate",),
        icon="mdi:calendar",
    ),
    AptiParkingVisitFieldDescription(
        key="in_date",
        name="입차일시",
        source_keys=("carInDate",),
        icon="mdi:car-arrow-right",
    ),
    AptiParkingVisitFieldDescription(
        key="out_date",
        name="출차일시",
        source_keys=("carOutDate",),
        icon="mdi:car-arrow-left",
    ),
    AptiParkingVisitFieldDescription(
        key="parked_minutes",
        name="주차시간",
        source_keys=("parkedTimeLong", "parkedTime"),
        icon="mdi:car-clock",
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    AptiParkingVisitFieldDescription(
        key="discount_minutes",
        name="할인시간",
        source_keys=("discountTime",),
        icon="mdi:ticket-percent",
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    AptiParkingVisitFieldDescription(
        key="calc_minutes",
        name="정산시간",
        source_keys=("calcTime",),
        icon="mdi:calculator-variant-outline",
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    AptiParkingVisitFieldDescription(
        key="visit_type",
        name="방문유형",
        source_keys=("visitType",),
        icon="mdi:card-account-details-outline",
    ),
)


STATIC_SENSORS: tuple[AptiSensorDescription, ...] = (
    AptiSensorDescription(
        key="account_user_id",
        name="회원 ID",
        icon="mdi:account",
        device_key=DEVICE_ACCOUNT,
        value_fn=lambda d: _safe_text(d.get("account", {}).get("userId")),
    ),
    AptiSensorDescription(
        key="account_apt_code",
        name="단지 코드",
        icon="mdi:identifier",
        device_key=DEVICE_ACCOUNT,
        value_fn=lambda d: _safe_text(d.get("account", {}).get("code")),
    ),
    AptiSensorDescription(
        key="mgmt_month_fee",
        name="당월 관리비",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        device_key=DEVICE_MANAGEMENT_FEE,
        value_fn=lambda d: _safe_int(d.get("manage_home", {}).get("monthFee")),
    ),
    AptiSensorDescription(
        key="mgmt_previous_month_fee",
        name="전월 관리비",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        device_key=DEVICE_MANAGEMENT_FEE,
        value_fn=lambda d: _safe_int(d.get("manage_home", {}).get("bfMonthFee")),
    ),
    AptiSensorDescription(
        key="mgmt_due_fee",
        name="납부 대상 금액",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        device_key=DEVICE_MANAGEMENT_FEE,
        value_fn=lambda d: _safe_int(d.get("manage_home", {}).get("bfDueFee")),
    ),
    AptiSensorDescription(
        key="mgmt_discount_total",
        name="총 할인 금액",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        device_key=DEVICE_MANAGEMENT_FEE,
        value_fn=lambda d: _safe_int(
            d.get("management_fee", {}).get("discount", {}).get("discountFee")
        ),
    ),
    AptiSensorDescription(
        key="mgmt_bill_month",
        name="청구월",
        icon="mdi:calendar-month",
        device_key=DEVICE_MANAGEMENT_FEE,
        value_fn=lambda d: _safe_text(d.get("manage_home", {}).get("billYm")),
    ),
    AptiSensorDescription(
        key="mgmt_due_date",
        name="관리비 마감일",
        device_class=SensorDeviceClass.DATE,
        device_key=DEVICE_MANAGEMENT_FEE,
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
        device_key=DEVICE_MANAGEMENT_FEE,
        value_fn=lambda d: _safe_float(d.get("manage_home", {}).get("area")),
    ),
    AptiSensorDescription(
        key="energy_my_fee",
        name="에너지 요금(우리집)",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        device_key=DEVICE_ENERGY,
        value_fn=lambda d: _safe_int(
            d.get("manage_home", {}).get("energyCondition", {}).get("myFee")
        ),
    ),
    AptiSensorDescription(
        key="energy_avg_fee",
        name="에너지 요금(평균)",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        device_key=DEVICE_ENERGY,
        value_fn=lambda d: _safe_int(
            d.get("manage_home", {}).get("energyCondition", {}).get("avgFee")
        ),
    ),
    AptiSensorDescription(
        key="energy_compared_avg",
        name="평균 대비 에너지 사용",
        native_unit_of_measurement=PERCENTAGE,
        device_key=DEVICE_ENERGY,
        value_fn=lambda d: _safe_int(
            d.get("manage_home", {}).get("energyCondition", {}).get("compAvg")
        ),
    ),
    AptiSensorDescription(
        key="parking_parked_minutes",
        name="누적 주차시간",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:car-clock",
        device_key=DEVICE_PARKING,
        value_fn=lambda d: _safe_int(d.get("parking_visit", {}).get("parkedTime")),
    ),
    AptiSensorDescription(
        key="parking_remaining_minutes",
        name="무료 잔여시간",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-sand",
        device_key=DEVICE_PARKING,
        value_fn=lambda d: _safe_int(d.get("parking_visit", {}).get("remainTime")),
    ),
    AptiSensorDescription(
        key="parking_expected_fee",
        name="예상 주차요금",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        device_key=DEVICE_PARKING,
        value_fn=lambda d: _safe_int(d.get("parking_visit", {}).get("expectedParkingFee")),
    ),
    AptiSensorDescription(
        key="parking_based_minutes",
        name="주차 기본시간",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:clock-outline",
        device_key=DEVICE_PARKING,
        value_fn=lambda d: _safe_int(d.get("parking_visit", {}).get("basedMinutes")),
    ),
    AptiSensorDescription(
        key="parking_based_minutes_fare",
        name="주차 기본단가",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        device_key=DEVICE_PARKING,
        value_fn=lambda d: _safe_int(d.get("parking_visit", {}).get("basedMinutesFare")),
    ),
    AptiSensorDescription(
        key="parking_visit_vehicle_count",
        name="방문차량 건수",
        icon="mdi:car-multiple",
        device_key=DEVICE_PARKING,
        value_fn=lambda d: len(_parking_visit_rows(d)),
    ),
    AptiSensorDescription(
        key="payment_history_latest_bill_month",
        name="최근 납부월",
        icon="mdi:calendar-check",
        device_key=DEVICE_PAYMENT,
        value_fn=lambda d: _safe_text((_get_latest_payment_row(d) or {}).get("billYm")),
    ),
    AptiSensorDescription(
        key="payment_history_latest_paid_date",
        name="최근 납부일",
        device_class=SensorDeviceClass.DATE,
        device_key=DEVICE_PAYMENT,
        value_fn=lambda d: _parse_yyyymmdd((_get_latest_payment_row(d) or {}).get("payDate")),
    ),
    AptiSensorDescription(
        key="payment_history_latest_paid_amount",
        name="최근 납부금액",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        device_key=DEVICE_PAYMENT,
        value_fn=lambda d: _safe_int((_get_latest_payment_row(d) or {}).get("amt")),
    ),
    AptiSensorDescription(
        key="payment_next_bill_month",
        name="다음 청구월",
        icon="mdi:calendar-arrow-right",
        device_key=DEVICE_PAYMENT,
        value_fn=lambda d: _safe_text(d.get("manage_payment_next", {}).get("nextBillYm")),
    ),
    AptiSensorDescription(
        key="payment_my_cash",
        name="보유 캐시",
        native_unit_of_measurement=CURRENCY_KRW,
        device_class=SensorDeviceClass.MONETARY,
        device_key=DEVICE_PAYMENT,
        value_fn=lambda d: _safe_int(d.get("manage_payment_next", {}).get("myCash")),
    ),
    AptiSensorDescription(
        key="payment_coupon_count",
        name="보유 쿠폰수",
        icon="mdi:ticket-percent",
        device_key=DEVICE_PAYMENT,
        value_fn=lambda d: _safe_int(d.get("manage_payment_next", {}).get("couponCnt")),
    ),
    AptiSensorDescription(
        key="autodiscount_honey",
        name="꿀단지 할인 사용",
        icon="mdi:honey-outline",
        device_key=DEVICE_MANAGEMENT_FEE,
        value_fn=lambda d: _safe_text(d.get("manage_auto_discount", {}).get("honeyYn")),
    ),
    AptiSensorDescription(
        key="autodiscount_schedule_month",
        name="자동할인 예정월",
        icon="mdi:calendar-star",
        device_key=DEVICE_MANAGEMENT_FEE,
        value_fn=lambda d: _safe_text(d.get("manage_auto_discount", {}).get("schBillYm")),
    ),
    AptiSensorDescription(
        key="refresh_interval_minutes",
        name="갱신 주기",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:update",
        device_key=DEVICE_SYSTEM,
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
        super().__init__(
            coordinator,
            config_entry,
            f"sensor_{description.key}",
            device_key=description.device_key,
        )
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
        super().__init__(
            coordinator,
            config_entry,
            f"detail_fee_{item_no}_{slugify(item_name)}",
            device_key=DEVICE_MANAGEMENT_FEE,
        )
        self._item_no = item_no
        self._item_name = item_name
        self._attr_name = f"관리비 {item_name}"

    def _get_item(self) -> dict[str, Any] | None:
        return _find_management_detail_item(self.coordinator.data, self._item_no)

    @property
    def native_value(self) -> int | None:
        item = self._get_item()
        return _safe_int(item.get("fee")) if item else None


class AptiManagementDetailMetaSensor(AptiCoordinatorEntity, SensorEntity):
    """Expose per-item metadata from management fee detail as entities."""

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        item_no: str,
        item_name: str,
        metric: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            f"detail_meta_{item_no}_{slugify(item_name)}_{metric}",
            device_key=DEVICE_MANAGEMENT_FEE,
        )
        self._item_no = item_no
        self._metric = metric

        if metric == "item_no":
            self._attr_name = f"{item_name} 항목 코드"
            self._attr_icon = "mdi:identifier"
        elif metric == "usage":
            self._attr_name = f"{item_name} 사용량"
            self._attr_icon = "mdi:gauge"
        elif metric == "increase":
            self._attr_name = f"{item_name} 증감"
            self._attr_icon = "mdi:chart-line"
        else:
            self._attr_name = f"{item_name} 단위"
            self._attr_icon = "mdi:ruler"

    def _item(self) -> dict[str, Any] | None:
        return _find_management_detail_item(self.coordinator.data, self._item_no)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self._metric != "usage":
            return None
        item = self._item()
        return _safe_text(item.get("unit")) if item else None

    @property
    def native_value(self) -> int | float | str | None:
        item = self._item()
        if not item:
            return None

        if self._metric == "item_no":
            return _safe_text(item.get("itemNo"))
        if self._metric == "usage":
            return _safe_float(item.get("usage"))
        if self._metric == "increase":
            return _safe_float(item.get("increase"))
        return _safe_text(item.get("unit"))


class AptiManagementDetailSubItemSensor(AptiCoordinatorEntity, SensorEntity):
    """Expose sub-item values under management fee detail."""

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        item_no: str,
        item_name: str,
        sub_index: int,
        sub_title: str,
        value_key: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            (
                f"detail_sub_item_{item_no}_{slugify(item_name)}_"
                f"{sub_index}_{slugify(sub_title)}_{slugify(value_key)}"
            ),
            device_key=DEVICE_MANAGEMENT_FEE,
        )
        self._item_no = item_no
        self._sub_index = sub_index
        self._value_key = value_key

        self._attr_name = f"{item_name} {sub_title}"
        self._attr_icon = "mdi:cash-plus"

        if value_key in {"amt", "fee", "amount"}:
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_native_unit_of_measurement = CURRENCY_KRW
        elif value_key.endswith("Time") or value_key.endswith("Minutes"):
            self._attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def _sub_item(self) -> tuple[dict[str, Any], dict[str, Any]] | None:
        parent = _find_management_detail_item(self.coordinator.data, self._item_no)
        if not parent:
            return None

        rows = parent.get("list", [])
        if not isinstance(rows, list):
            return None

        index = self._sub_index - 1
        if index < 0 or index >= len(rows):
            return None

        row = rows[index]
        if not isinstance(row, dict):
            return None
        return parent, row

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self._value_key != "usage":
            return self._attr_native_unit_of_measurement

        data = self._sub_item()
        if not data:
            return None
        parent, row = data

        unit = _safe_text(row.get("unit"))
        if unit:
            return unit
        return _safe_text(parent.get("unit"))

    @property
    def native_value(self) -> int | float | str | None:
        data = self._sub_item()
        if not data:
            return None

        _, row = data
        value = row.get(self._value_key)
        if value is None:
            return None

        if self._value_key in {"amt", "fee", "amount"}:
            return _safe_int(value)

        int_value = _safe_int(value)
        if int_value is not None:
            return int_value

        float_value = _safe_float(value)
        if float_value is not None:
            return float_value

        return _safe_text(value)


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
        super().__init__(
            coordinator,
            config_entry,
            unique,
            device_key=DEVICE_MANAGEMENT_FEE,
        )
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


class AptiPaymentStateSensor(AptiCoordinatorEntity, SensorEntity):
    """Sensors per payment history state code."""

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        state_code: str,
        metric: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            f"payment_state_{state_code}_{metric}",
            device_key=DEVICE_PAYMENT,
        )
        self._state_code = state_code
        self._metric = metric

        if metric == "count":
            self._attr_name = f"납부이력 {state_code} 건수"
            self._attr_icon = "mdi:counter"
        elif metric == "amount":
            self._attr_name = f"납부이력 {state_code} 금액"
            self._attr_icon = "mdi:cash-multiple"
            self._attr_device_class = SensorDeviceClass.MONETARY
            self._attr_native_unit_of_measurement = CURRENCY_KRW
        elif metric == "state_name":
            self._attr_name = f"납부이력 {state_code} 상태명"
            self._attr_icon = "mdi:label-outline"
        elif metric == "latest_bill_month":
            self._attr_name = f"납부이력 {state_code} 최근 청구월"
            self._attr_icon = "mdi:calendar-month"
        else:
            self._attr_name = f"납부이력 {state_code} 최근 납부일"
            self._attr_icon = "mdi:calendar-check"
            self._attr_device_class = SensorDeviceClass.DATE

    def _rows(self) -> list[dict[str, Any]]:
        rows = self.coordinator.data.get("payment_histories", {}).get(self._state_code, [])
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    def _latest(self) -> dict[str, Any] | None:
        rows = self._rows()
        if not rows:
            return None
        return max(
            rows,
            key=lambda row: (
                str(row.get("payDate", "")),
                str(row.get("billYm", "")),
            ),
        )

    @property
    def native_value(self) -> int | str | date | None:
        rows = self._rows()

        if self._metric == "count":
            return len(rows)
        if self._metric == "amount":
            return sum(_safe_int(row.get("amt")) or 0 for row in rows)

        latest = self._latest()
        if not latest:
            return None

        if self._metric == "state_name":
            return _safe_text(latest.get("stateName"))
        if self._metric == "latest_bill_month":
            return _safe_text(latest.get("billYm"))
        return _parse_yyyymmdd(_safe_text(latest.get("payDate")))


class AptiParkingVisitDetailSensor(AptiCoordinatorEntity, SensorEntity):
    """Expose parking visit detail fields as standalone entities."""

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        visit_index: int,
        visit_key: str,
        field: AptiParkingVisitFieldDescription,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            f"parking_visit_{visit_index}_{slugify(visit_key)}_{field.key}",
            device_key=DEVICE_PARKING,
        )
        self._visit_index = visit_index
        self._field = field

        self._attr_name = f"방문차량 {visit_index} {field.name}"
        self._attr_icon = field.icon
        self._attr_native_unit_of_measurement = field.native_unit_of_measurement
        self._attr_device_class = field.device_class

    def _visit(self) -> dict[str, Any] | None:
        rows = _parking_visit_rows(self.coordinator.data)
        index = self._visit_index - 1
        if index < 0 or index >= len(rows):
            return None
        return rows[index]

    @property
    def native_value(self) -> int | str | date | None:
        row = self._visit()
        if not row:
            return None

        value = _pick_scalar_value(row, self._field.source_keys)
        if value is None:
            return None

        if self._field.device_class == SensorDeviceClass.DATE:
            return _parse_yyyymmdd(_safe_text(value))

        if self._field.native_unit_of_measurement == UnitOfTime.MINUTES:
            return _safe_int(value)

        return _safe_text(value)


class AptiEnergySensor(AptiCoordinatorEntity, SensorEntity):
    """Fee/usage sensor for a single energy category."""

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        energy_key: str,
        metric: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            f"energy_{energy_key}_{metric}",
            device_key=DEVICE_ENERGY,
        )
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
        return _safe_text(item.get("unit"))

    @property
    def native_value(self) -> int | float | None:
        item = self._energy_obj()
        if not item:
            return None
        value = item.get(self._metric)
        if self._metric == "fee":
            return _safe_int(value)
        return _safe_float(value)


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
        entities.append(
            AptiPaymentStateSensor(coordinator, config_entry, state_code, "state_name")
        )
        entities.append(
            AptiPaymentStateSensor(coordinator, config_entry, state_code, "latest_bill_month")
        )
        entities.append(
            AptiPaymentStateSensor(coordinator, config_entry, state_code, "latest_paid_date")
        )

    for energy_key in ("electric", "water", "heat", "hotwater"):
        entities.append(AptiEnergySensor(coordinator, config_entry, energy_key, "fee"))
        entities.append(AptiEnergySensor(coordinator, config_entry, energy_key, "use"))

    detail_items = _management_detail_rows(coordinator.data)
    for item in detail_items:
        item_no = _safe_text(item.get("itemNo"))
        item_name = _safe_text(item.get("itemName"))
        if not item_no or not item_name:
            continue

        entities.append(AptiManagementDetailFeeSensor(coordinator, config_entry, item_no, item_name))

        for metric in ("item_no", "usage", "increase", "unit"):
            entities.append(
                AptiManagementDetailMetaSensor(
                    coordinator,
                    config_entry,
                    item_no,
                    item_name,
                    metric,
                )
            )

        sub_items = item.get("list", [])
        if not isinstance(sub_items, list):
            continue

        for sub_index, sub_item in enumerate(sub_items, start=1):
            if not isinstance(sub_item, dict):
                continue

            sub_title = _safe_text(
                sub_item.get("title") or sub_item.get("itemName") or sub_item.get("name")
            ) or f"세부항목{sub_index}"

            value_key = _pick_dynamic_value_key(
                sub_item,
                preferred=("amt", "fee", "amount", "usage", "value"),
            )
            if not value_key:
                continue

            entities.append(
                AptiManagementDetailSubItemSensor(
                    coordinator,
                    config_entry,
                    item_no,
                    item_name,
                    sub_index,
                    sub_title,
                    value_key,
                )
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

    for visit_index, row in enumerate(_parking_visit_rows(coordinator.data), start=1):
        visit_key = _safe_text(row.get("carNoInformation")) or f"visit_{visit_index}"
        for field in PARKING_VISIT_FIELDS:
            entities.append(
                AptiParkingVisitDetailSensor(
                    coordinator,
                    config_entry,
                    visit_index,
                    visit_key,
                    field,
                )
            )

    async_add_entities(entities)
