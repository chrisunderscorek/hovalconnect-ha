"""Hoval Connect Climate entities."""
from __future__ import annotations
import logging
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, MANUFACTURER, TEMP_DURATION_DEFAULT

_LOGGER = logging.getLogger(__name__)

STATUS_TO_ACTION = {
    "heating":  HVACAction.HEATING,
    "cooling":  HVACAction.COOLING,
    "charging": HVACAction.HEATING,  # Warmwasser lädt
    "off":      HVACAction.IDLE,
    None:       HVACAction.IDLE,
}

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    circuits = data["coordinator"].data.get("circuits", [])
    entities = [
        HovalCircuitClimate(data["coordinator"], data["api"], data["plant_id"], c)
        for c in circuits if c.get("selectable") and c.get("type") in ("HK", "WW")
    ]
    async_add_entities(entities)

class HovalCircuitClimate(CoordinatorEntity, ClimateEntity):
    _attr_hvac_modes = [HVACMode.AUTO]
    _attr_hvac_mode  = HVACMode.AUTO
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, coordinator, api, plant_id, circuit):
        super().__init__(coordinator)
        self._api = api
        self._plant_id = plant_id
        self._path = circuit["path"]
        self._circuit_type = circuit.get("type")
        name = circuit.get("name") or self._circuit_type
        self._attr_name = f"Hoval {name}"
        self._attr_unique_id = f"hoval_{plant_id}_{self._path}_climate"
        self._attr_min_temp = 10.0
        self._attr_max_temp = 70.0 if self._circuit_type == "WW" else 30.0

    def _c(self):
        for c in self.coordinator.data.get("circuits", []):
            if c["path"] == self._path:
                return c
        return {}

    @property
    def current_temperature(self): return self._c().get("actualValue")
    @property
    def target_temperature(self): return self._c().get("targetValue")
    @property
    def hvac_action(self): return STATUS_TO_ACTION.get(self._c().get("circuitStatus"), HVACAction.IDLE)

    @property
    def extra_state_attributes(self):
        c = self._c()
        return {
            "active_program":   c.get("activeProgram"),
            "week_program":     c.get("activeWeekProgramName"),
            "day_program":      c.get("activeDayProgramName"),
            "operation_mode":   c.get("operationMode"),
            "has_error":        c.get("hasError"),
        }

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get("temperature")
        if temp is None:
            return
        if self._circuit_type == "WW":
            # Warmwasser: immer dauerhaft
            await self._api.set_constant_temp(self._plant_id, self._path, temp)
        else:
            # Heizkreis: abhängig vom aktiven Programm
            active_program = self._c().get("activeProgram", "week1")
            if active_program == "constant":
                await self._api.set_constant_temp(self._plant_id, self._path, temp)
            else:
                await self._api.set_temporary_change(self._plant_id, self._path, temp, TEMP_DURATION_DEFAULT)
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._plant_id)},
            "name": "Hoval Belaria Compact IR",
            "manufacturer": MANUFACTURER,
            "model": "Belaria Compact IR",
        }
