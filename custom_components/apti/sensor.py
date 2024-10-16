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
from .helper import find_value_by_condition, get_icon


@dataclass(kw_only=True)
class APTiSensorEntityDescription(SensorEntityDescription):
    """Describes APT.i sensor entity."""

    format_id: str     # unique_id
    chepter_name: str  # device_info
    exists_fn: Callable[..., bool] = lambda _: True
    icon_fn: Callable[..., str] = lambda _: None
    trans_ph: Callable[..., dict] = lambda _: {}
    value_fn: Callable[..., datetime | str]


SENSORS: tuple[APTiSensorEntityDescription, ...] = (
    APTiSensorEntityDescription(
        key="maint_item",
        translation_key="maint_item",
        native_unit_of_measurement="원",
        format_id=lambda k: f"{k['항목']}_maint_item",
        chepter_name="관리비",
        icon_fn=lambda c, k: get_icon(c, k["항목"]),
        trans_ph=lambda k: {"category": k["항목"]},
        value_fn=lambda v: find_value_by_condition(v, lambda k: k.startswith("당월")),
    ),
    APTiSensorEntityDescription(
        key="maint_payment",
        icon="mdi:currency-krw",
        translation_key="maint_payment",
        native_unit_of_measurement="원",
        format_id="maint_payment",
        chepter_name="관리비",
        value_fn=lambda v: find_value_by_condition(v, lambda k: k.startswith("납부할 금액")),
    ),
    APTiSensorEntityDescription(
        key="energy_usage",
        icon="mdi:flash",
        translation_key="energy_usage",
        native_unit_of_measurement="원",
        format_id="energy_usage",
        chepter_name="에너지",
        value_fn=lambda v: find_value_by_condition(v, lambda k: k.endswith("사용")),
    ),
    APTiSensorEntityDescription(
        key="energy_detail",
        translation_key="energy_detail",
        native_unit_of_measurement="",
        format_id=lambda k: f"{k['유형']}_energy_detail",
        chepter_name="에너지",
        icon_fn=lambda c, k: get_icon(c, k["유형"]),
        trans_ph=lambda k: {"category": k["유형"]},
        value_fn=lambda v: find_value_by_condition(v, lambda k: k.startswith("사용량")),
    ),
    APTiSensorEntityDescription(
        key="energy_type",
        translation_key="energy_type",
        native_unit_of_measurement="원",
        format_id=lambda k: f"{k['유형']}_energy_type",
        chepter_name="에너지",
        icon_fn=lambda c, k: get_icon(c, k["유형"]),
        trans_ph=lambda k: {"category": k["유형"]},
        value_fn=lambda v: find_value_by_condition(v, lambda k: k.startswith("총액")),
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
        self._value = coordinator.data[self.description.key]

        self._attr_extra_state_attributes = self._value
        self._attr_unique_id = self.description.format_id

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.description.value_fn(self._value)


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
        
        self._attr_extra_state_attributes = category
        self._attr_translation_placeholders = self.description.trans_ph(category)
        self._attr_unique_id = self.description.format_id(category)
    
    async def async_added_to_hass(self) -> None:
        """Called when added to Hass."""
        await self.async_set_icon()
        await super().async_added_to_hass()
    
    async def async_set_icon(self) -> None:
        """Update the icon asynchronously."""
        self._attr_icon = await self.description.icon_fn(
            self.description.key, self.category
        )
    
    @property
    def native_value(self) -> datetime | str:
        """Return the state of the sensor."""
        return self.description.value_fn(self.category)
