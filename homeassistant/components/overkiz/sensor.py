"""Support for Overkiz sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from pyoverkiz.enums import OverkizAttribute, OverkizState, UIWidget
from pyoverkiz.types import StateType as OverkizStateType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    ENERGY_WATT_HOUR,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    SIGNAL_STRENGTH_DECIBELS,
    TEMP_CELSIUS,
    TIME_SECONDS,
    VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
    VOLUME_LITERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import HomeAssistantOverkizData
from .const import DOMAIN, IGNORED_OVERKIZ_DEVICES, OVERKIZ_STATE_TO_TRANSLATION
from .coordinator import OverkizDataUpdateCoordinator
from .entity import OverkizDescriptiveEntity, OverkizDeviceClass, OverkizEntity


@dataclass
class OverkizSensorDescription(SensorEntityDescription):
    """Class to describe an Overkiz sensor."""

    native_value: Callable[[OverkizStateType], StateType] | None = None


SENSOR_DESCRIPTIONS: list[OverkizSensorDescription] = [
    OverkizSensorDescription(
        key=OverkizState.CORE_BATTERY_LEVEL,
        name="Battery level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_value=lambda value: int(float(str(value).strip("%"))),
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_BATTERY,
        name="Battery",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:battery",
        device_class=OverkizDeviceClass.BATTERY,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_RSSI_LEVEL,
        name="RSSI level",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_value=lambda value: round(cast(float, value)),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_EXPECTED_NUMBER_OF_SHOWER,
        name="Expected number of shower",
        icon="mdi:shower-head",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_NUMBER_OF_SHOWER_REMAINING,
        name="Number of shower remaining",
        icon="mdi:shower-head",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # V40 is measured in litres (L) and shows the amount of warm (mixed) water with a temperature of 40 C, which can be drained from a switched off electric water heater.
    OverkizSensorDescription(
        key=OverkizState.CORE_V40_WATER_VOLUME_ESTIMATION,
        name="Water volume estimation at 40 °C",
        icon="mdi:water",
        native_unit_of_measurement=VOLUME_LITERS,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_WATER_CONSUMPTION,
        name="Water consumption",
        icon="mdi:water",
        native_unit_of_measurement=VOLUME_LITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.IO_OUTLET_ENGINE,
        name="Outlet engine",
        icon="mdi:fan-chevron-down",
        native_unit_of_measurement=VOLUME_LITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.IO_INLET_ENGINE,
        name="Inlet engine",
        icon="mdi:fan-chevron-up",
        native_unit_of_measurement=VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.HLRRWIFI_ROOM_TEMPERATURE,
        name="Room temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    OverkizSensorDescription(
        key=OverkizState.IO_MIDDLE_WATER_TEMPERATURE,
        name="Middle water temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_FOSSIL_ENERGY_CONSUMPTION,
        name="Fossil energy consumption",
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_GAS_CONSUMPTION,
        name="Gas consumption",
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_THERMAL_ENERGY_CONSUMPTION,
        name="Thermal energy consumption",
    ),
    # LightSensor/LuminanceSensor
    OverkizSensorDescription(
        key=OverkizState.CORE_LUMINANCE,
        name="Luminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,  # core:MeasuredValueType = core:LuminanceInLux
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # ElectricitySensor/CumulativeElectricPowerConsumptionSensor
    OverkizSensorDescription(
        key=OverkizState.CORE_ELECTRIC_ENERGY_CONSUMPTION,
        name="Electric energy consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_WATT_HOUR,  # core:MeasuredValueType = core:ElectricalEnergyInWh (not for modbus:YutakiV2DHWElectricalEnergyConsumptionComponent)
        state_class=SensorStateClass.TOTAL_INCREASING,  # core:MeasurementCategory attribute = electric/overall
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_ELECTRIC_POWER_CONSUMPTION,
        name="Electric power consumption",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=POWER_WATT,  # core:MeasuredValueType = core:ElectricalEnergyInWh (not for modbus:YutakiV2DHWElectricalEnergyConsumptionComponent)
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_CONSUMPTION_TARIFF1,
        name="Consumption tariff 1",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_WATT_HOUR,  # core:MeasuredValueType = core:ElectricalEnergyInWh
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_CONSUMPTION_TARIFF2,
        name="Consumption tariff 2",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_WATT_HOUR,  # core:MeasuredValueType = core:ElectricalEnergyInWh
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_CONSUMPTION_TARIFF3,
        name="Consumption tariff 3",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_WATT_HOUR,  # core:MeasuredValueType = core:ElectricalEnergyInWh
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_CONSUMPTION_TARIFF4,
        name="Consumption tariff 4",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_WATT_HOUR,  # core:MeasuredValueType = core:ElectricalEnergyInWh
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_CONSUMPTION_TARIFF5,
        name="Consumption tariff 5",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_WATT_HOUR,  # core:MeasuredValueType = core:ElectricalEnergyInWh
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_CONSUMPTION_TARIFF6,
        name="Consumption tariff 6",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_WATT_HOUR,  # core:MeasuredValueType = core:ElectricalEnergyInWh
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_CONSUMPTION_TARIFF7,
        name="Consumption tariff 7",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_WATT_HOUR,  # core:MeasuredValueType = core:ElectricalEnergyInWh
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_CONSUMPTION_TARIFF8,
        name="Consumption tariff 8",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_WATT_HOUR,  # core:MeasuredValueType = core:ElectricalEnergyInWh
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_CONSUMPTION_TARIFF9,
        name="Consumption tariff 9",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_WATT_HOUR,  # core:MeasuredValueType = core:ElectricalEnergyInWh
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # HumiditySensor/RelativeHumiditySensor
    OverkizSensorDescription(
        key=OverkizState.CORE_RELATIVE_HUMIDITY,
        name="Relative humidity",
        native_value=lambda value: round(cast(float, value), 2),
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,  # core:MeasuredValueType = core:RelativeValueInPercentage
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # TemperatureSensor/TemperatureSensor
    OverkizSensorDescription(
        key=OverkizState.CORE_TEMPERATURE,
        name="Temperature",
        native_value=lambda value: round(cast(float, value), 2),
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,  # core:MeasuredValueType = core:TemperatureInCelcius
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # WeatherSensor/WeatherForecastSensor
    OverkizSensorDescription(
        key=OverkizState.CORE_WEATHER_STATUS,
        name="Weather status",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_MINIMUM_TEMPERATURE,
        name="Minimum temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_MAXIMUM_TEMPERATURE,
        name="Maximum temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # AirSensor/COSensor
    OverkizSensorDescription(
        key=OverkizState.CORE_CO_CONCENTRATION,
        name="CO concentration",
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # AirSensor/CO2Sensor
    OverkizSensorDescription(
        key=OverkizState.CORE_CO2_CONCENTRATION,
        name="CO2 concentration",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # SunSensor/SunEnergySensor
    OverkizSensorDescription(
        key=OverkizState.CORE_SUN_ENERGY,
        name="Sun energy",
        native_value=lambda value: round(cast(float, value), 2),
        icon="mdi:solar-power",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # WindSensor/WindSpeedSensor
    OverkizSensorDescription(
        key=OverkizState.CORE_WIND_SPEED,
        name="Wind speed",
        native_value=lambda value: round(cast(float, value), 2),
        icon="mdi:weather-windy",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # SmokeSensor/SmokeSensor
    OverkizSensorDescription(
        key=OverkizState.IO_SENSOR_ROOM,
        name="Sensor room",
        device_class=OverkizDeviceClass.SENSOR_ROOM,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:spray-bottle",
    ),
    OverkizSensorDescription(
        key=OverkizState.IO_PRIORITY_LOCK_ORIGINATOR,
        name="Priority lock originator",
        device_class=OverkizDeviceClass.PRIORITY_LOCK_ORIGINATOR,
        icon="mdi:lock",
        entity_registry_enabled_default=False,
        native_value=lambda value: OVERKIZ_STATE_TO_TRANSLATION.get(
            cast(str, value), cast(str, value)
        ),
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_PRIORITY_LOCK_TIMER,
        name="Priority lock timer",
        icon="mdi:lock-clock",
        native_unit_of_measurement=TIME_SECONDS,
        entity_registry_enabled_default=False,
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_DISCRETE_RSSI_LEVEL,
        name="Discrete RSSI level",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=OverkizDeviceClass.DISCRETE_RSSI_LEVEL,
        icon="mdi:wifi",
    ),
    OverkizSensorDescription(
        key=OverkizState.CORE_SENSOR_DEFECT,
        name="Sensor defect",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=OverkizDeviceClass.SENSOR_DEFECT,
        native_value=lambda value: OVERKIZ_STATE_TO_TRANSLATION.get(
            cast(str, value), cast(str, value)
        ),
    ),
    # DomesticHotWaterProduction/WaterHeatingSystem
    OverkizSensorDescription(
        key=OverkizState.IO_HEAT_PUMP_OPERATING_TIME,
        name="Heat pump operating time",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=TIME_SECONDS,
    ),
    OverkizSensorDescription(
        key=OverkizState.IO_ELECTRIC_BOOSTER_OPERATING_TIME,
        name="Electric booster operating time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=TIME_SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Cover
    OverkizSensorDescription(
        key=OverkizState.CORE_TARGET_CLOSURE,
        name="Target closure",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    # ThreeWayWindowHandle/WindowHandle
    OverkizSensorDescription(
        key=OverkizState.CORE_THREE_WAY_HANDLE_DIRECTION,
        name="Three way handle direction",
        device_class=OverkizDeviceClass.THREE_WAY_HANDLE_DIRECTION,
    ),
]

SUPPORTED_STATES = {description.key: description for description in SENSOR_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Overkiz sensors from a config entry."""
    data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []

    for device in data.coordinator.data.values():
        if device.widget == UIWidget.HOMEKIT_STACK:
            entities.append(
                OverkizHomeKitSetupCodeSensor(
                    device.device_url,
                    data.coordinator,
                )
            )

        if (
            device.widget in IGNORED_OVERKIZ_DEVICES
            or device.ui_class in IGNORED_OVERKIZ_DEVICES
        ):
            continue

        for state in device.definition.states:
            if description := SUPPORTED_STATES.get(state.qualified_name):
                entities.append(
                    OverkizStateSensor(
                        device.device_url,
                        data.coordinator,
                        description,
                    )
                )

    async_add_entities(entities)


class OverkizStateSensor(OverkizDescriptiveEntity, SensorEntity):
    """Representation of an Overkiz Sensor."""

    entity_description: OverkizSensorDescription

    @property
    def native_value(self) -> StateType:
        """Return the value of the sensor."""
        state = self.device.states.get(self.entity_description.key)

        if not state or not state.value:
            return None

        # Transform the value with a lambda function
        if self.entity_description.native_value:
            return self.entity_description.native_value(state.value)

        if isinstance(state.value, (dict, list)):
            return None

        return state.value


class OverkizHomeKitSetupCodeSensor(OverkizEntity, SensorEntity):
    """Representation of an Overkiz HomeKit Setup Code."""

    _attr_icon = "mdi:shield-home"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, device_url: str, coordinator: OverkizDataUpdateCoordinator
    ) -> None:
        """Initialize the device."""
        super().__init__(device_url, coordinator)
        self._attr_name = "HomeKit setup code"

    @property
    def native_value(self) -> str | None:
        """Return the value of the sensor."""
        if state := self.device.attributes.get(OverkizAttribute.HOMEKIT_SETUP_CODE):
            return cast(str, state.value)
        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
        # By default this sensor will be listed at a virtual HomekitStack device,
        # but it makes more sense to show this at the gateway device in the entity registry.
        return {
            "identifiers": {(DOMAIN, self.executor.get_gateway_id())},
        }
