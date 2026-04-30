"""Hoval Connect Select entities — Programm wählen."""
from __future__ import annotations
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
from .localization import device_info, program_names, program_select_suffix

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    circuits = data["coordinator"].data.get("circuits", [])
    entities = [
        HovalProgramSelect(data["coordinator"], data["api"], entry, data["plant_id"], c, hass.config.language)
        for c in circuits if c.get("selectable") and c.get("type") in ("HK", "WW")
    ]
    async_add_entities(entities)

class HovalProgramSelect(CoordinatorEntity, SelectEntity):
    def __init__(self, coordinator, api, entry, plant_id, circuit, hass_language):
        super().__init__(coordinator)
        self._api = api
        self._plant_id = plant_id
        self._path = circuit["path"]
        self._program_names = program_names(entry, hass_language)
        self._attr_options = list(self._program_names.values())
        name = circuit.get("name") or "Heating Circuit"
        self._attr_name = f"Hoval {name} {program_select_suffix(entry, hass_language)}"
        self._attr_unique_id = f"hoval_{plant_id}_{self._path}_program"

    def _c(self):
        for c in self.coordinator.data.get("circuits", []):
            if c["path"] == self._path:
                return c
        return {}

    @property
    def current_option(self):
        active = self._c().get("activeProgram", "week1")
        return self._program_names.get(active, active)

    async def async_select_option(self, option: str) -> None:
        # Reverse lookup: localized label to the stable API program key.
        key = next((k for k, v in self._program_names.items() if v == option), option)
        await self._api.set_program(self._plant_id, self._path, key)
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self):
        c = self._c()
        return {
            "week_program": c.get("activeWeekProgramName"),
            "day_program":  c.get("activeDayProgramName"),
        }

    @property
    def device_info(self):
        return device_info(self.coordinator, self._plant_id)
