"""Hoval Connect Sensor entities."""
from __future__ import annotations
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, MANUFACTURER

# Live value sensor definitions per circuit type
# Format: (key, translation_key, unit, device_class, state_class)
LIVE_SENSORS = {
    "HK": [
        ("outgoingTempActual", "flow_temp_actual",    UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
        ("outgoingTempTarget", "flow_temp_target",    UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
        ("roomTempActual",     "room_temp_actual",    UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
        ("roomTempTarget",     "room_temp_target",    UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
        ("outsideTemperature", "outside_temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    ],
    "BL": [
        ("tempActual",           "generator_temp_actual",    UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
        ("tempTarget",           "generator_temp_target",    UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
        ("modulation",           "modulation",               "%",                       None,                          SensorStateClass.MEASUREMENT),
        ("operatingHours",       "operating_hours",          "h",                       None,                          SensorStateClass.TOTAL_INCREASING),
        ("operationCycles",      "operation_cycles",         None,                      None,                          SensorStateClass.TOTAL_INCREASING),
        ("operatingHoursOver50", "operating_hours_over_50",  "h",                       None,                          SensorStateClass.TOTAL_INCREASING),
        ("faStatus",             "error_code",               None,                      None,                          None),
    ],
    "WW": [
        ("tempSf1Actual", "storage_temp_actual", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
        ("tempTarget",    "hot_water_temp_target", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    ],
}

# Circuit temperature sensor translation keys
CIRCUIT_TEMP_KEYS = {
    "actualValue": "circuit_temp_actual",
    "targetValue": "circuit_temp_target",
}

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    plant_id = data["plant_id"]
    entities = []

    for c in coordinator.data.get("circuits", []):
        path = c["path"]
        ctype = c.get("type", "")

        # Status sensor
        if c.get("circuitStatus") is not None:
            entities.append(HovalStatusSensor(coordinator, plant_id, path, ctype))

        # Program sensor
        if c.get("activeProgram") is not None:
            entities.append(HovalProgramSensor(coordinator, plant_id, path, ctype))

        # Temperature sensors from circuit data
        if c.get("actualValue") is not None:
            entities.append(HovalCircuitTempSensor(coordinator, plant_id, path, ctype, "actualValue"))
        # Hot water: skip targetValue here – already provided by live values
        if c.get("selectable") and c.get("targetValue") is not None and ctype != "WW":
            entities.append(HovalCircuitTempSensor(coordinator, plant_id, path, ctype, "targetValue"))

        # Live value sensors (modulation, temperatures, operating hours etc.)
        for key, translation_key, unit, dev_class, state_class in LIVE_SENSORS.get(ctype, []):
            entities.append(HovalLiveSensor(
                coordinator, plant_id, path, ctype,
                key, translation_key, unit, dev_class, state_class
            ))

    async_add_entities(entities)


class HovalCircuitTempSensor(CoordinatorEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class  = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True

    def __init__(self, coordinator, plant_id, path, ctype, key):
        super().__init__(coordinator)
        self._plant_id = plant_id
        self._path = path
        self._key = key
        self._attr_unique_id = f"hoval_{plant_id}_{path}_{key}"
        self._attr_translation_key = f"{ctype.lower()}_{CIRCUIT_TEMP_KEYS.get(key, key)}"

    @property
    def native_value(self):
        for c in self.coordinator.data.get("circuits", []):
            if c["path"] == self._path:
                return c.get(self._key)

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._plant_id)}, "name": "Hoval Belaria Compact IR", "manufacturer": MANUFACTURER}


class HovalLiveSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, plant_id, path, ctype, key, translation_key, unit, dev_class, state_class):
        super().__init__(coordinator)
        self._plant_id = plant_id
        self._path = path
        self._key = key
        self._attr_unique_id = f"hoval_{plant_id}_{path}_{key}"
        self._attr_translation_key = translation_key
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = dev_class
        self._attr_state_class = state_class

    @property
    def native_value(self):
        val = self.coordinator.data.get("live_values", {}).get(self._path, {}).get(self._key)
        if val is None:
            return None
        try:
            return float(val) if "." in str(val) else int(val)
        except (ValueError, TypeError):
            return val

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._plant_id)}, "name": "Hoval Belaria Compact IR", "manufacturer": MANUFACTURER}


class HovalStatusSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, plant_id, path, ctype):
        super().__init__(coordinator)
        self._plant_id = plant_id
        self._path = path
        self._attr_unique_id = f"hoval_{plant_id}_{path}_status"
        self._attr_translation_key = "circuit_status"

    def _c(self):
        for c in self.coordinator.data.get("circuits", []):
            if c["path"] == self._path:
                return c
        return {}

    @property
    def native_value(self): return self._c().get("circuitStatus")

    @property
    def extra_state_attributes(self):
        c = self._c()
        return {"operation_mode": c.get("operationMode"), "has_error": c.get("hasError")}

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._plant_id)}, "name": "Hoval Belaria Compact IR", "manufacturer": MANUFACTURER}


class HovalProgramSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, plant_id, path, ctype):
        super().__init__(coordinator)
        self._plant_id = plant_id
        self._path = path
        self._attr_unique_id = f"hoval_{plant_id}_{path}_active_program"
        self._attr_translation_key = "active_program"

    def _c(self):
        for c in self.coordinator.data.get("circuits", []):
            if c["path"] == self._path:
                return c
        return {}

    @property
    def native_value(self): return self._c().get("activeProgram")

    @property
    def extra_state_attributes(self):
        c = self._c()
        return {
            "week_program": c.get("activeWeekProgramName"),
            "day_program":  c.get("activeDayProgramName"),
        }

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._plant_id)}, "name": "Hoval Belaria Compact IR", "manufacturer": MANUFACTURER}
