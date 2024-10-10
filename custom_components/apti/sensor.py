"""APT.i Sensor Platform Integration."""

from typing import Any

from collections.abc import Callable
from datetime import datetime
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription

from .coordinator import APTiDataUpdateCoordinator
from .entity import APTiDevice
from .helper import find_value_by_condition


@dataclass(kw_only=True)
class APTiSensorEntityDescription(SensorEntityDescription):
    """Describes APT.i sensor entity."""

    format_id: str
    chepter_name: str
    exists_fn: Callable[..., bool] = lambda _: True
    value_fn: Callable[..., datetime | str]
    extra_attributes: Callable[..., dict] = lambda _: {}


SENSORS: tuple[APTiSensorEntityDescription, ...] = (
    APTiSensorEntityDescription(
        key="maint_item",
        translation_key="maint_item",
        translation_placeholders=lambda key: {"category": key["항목"]},
        format_id=lambda key: f"{key['항목']}_maint_item",
        chepter_name="관리비",
        unit_of_measurement = "원",
        value_fn=lambda value: find_value_by_condition(value, lambda k: k.startswith("당월")),
        extra_attributes=lambda value: value,
    ),
    APTiSensorEntityDescription(
        key="maint_payment",
        translation_key="maint_payment",
        format_id="maint_payment",
        chepter_name="관리비",
        unit_of_measurement = "원",
        value_fn=lambda value: find_value_by_condition(value, lambda k: k.startswith("납부할 금액")),
        extra_attributes=lambda value: value,
    ),
    APTiSensorEntityDescription(
        key="energy_usage",
        translation_key="energy_usage",
        format_id="energy_usage",
        chepter_name="에너지",
        unit_of_measurement = "원",
        value_fn=lambda value: find_value_by_condition(value, lambda k: k.endswith("사용")),
        extra_attributes=lambda value: value,
    ),
    APTiSensorEntityDescription(
        key="energy_detail",
        translation_key="energy_detail",
        translation_placeholders=lambda key: {"category": key["유형"]},
        format_id=lambda key: f"{key['유형']}_energy_detail",
        chepter_name="에너지",
        unit_of_measurement = "",
        value_fn=lambda value: find_value_by_condition(value, lambda k: k.startswith("사용량")),
        extra_attributes=lambda value: value,
    ),
    APTiSensorEntityDescription(
        key="energy_type",
        translation_key="energy_type",
        translation_placeholders=lambda key: {"category": key["유형"]},
        format_id=lambda key: f"{key['유형']}_energy_type",
        chepter_name="에너지",
        unit_of_measurement = "원",
        value_fn=lambda value: find_value_by_condition(value, lambda k: k.startswith("총액")),
        extra_attributes=lambda value: value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the sensor platform."""
    coordinator: APTiDataUpdateCoordinator = entry.runtime_data
    
    entities: list[APTiSensor] = []

    for sensor in SENSORS:
        if sensor.exists_fn(coordinator) and sensor.key in coordinator.data:
            sensor_data = coordinator.data[sensor.key]
            
            if isinstance(sensor_data, list):
                for category in sensor_data:
                    entities.append(APTiCategorySensor(coordinator, sensor, category))
            else:
                entities.append(APTiSensor(coordinator, sensor))
    
    if entities:
        async_add_entities(entities)


class APTiSensor(APTiDevice, SensorEntity):
    """APT.i sensor."""

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        entity_description: APTiSensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description)
        self.entity_description = entity_description

        self._attr_unique_id = self.description.format_id
        self._attr_extra_state_attributes = self.description.extra_attributes(
            coordinator.data[self.description.key]
        )

        self._attr_native_unit_of_measurement = self.description.unit_of_measurement

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        value = self.coordinator.data[self.description.key]
        return self.description.value_fn(value)


class APTiCategorySensor(APTiDevice, SensorEntity):
    """APT.i category sensor."""

    def __init__(
        self,
        coordinator: APTiDataUpdateCoordinator,
        entity_description: APTiSensorEntityDescription,
        category: list[dict]
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description)
        self.category = category
        self.entity_description = entity_description
        
        self._attr_unique_id = self.description.format_id(category)
        self._attr_extra_state_attributes = self.description.extra_attributes(
            category
        )

        self._attr_native_unit_of_measurement = self.description.unit_of_measurement

    @property
    def native_value(self) -> datetime | str:
        """Return the state of the sensor."""
        return self.description.value_fn(self.category)

    @property
    def translation_placeholders(self) -> dict[str, str] | None:
        """Return the translation placeholders."""
        if self.category:
            return self.description.translation_placeholders(
                self.category
            )
        return None
