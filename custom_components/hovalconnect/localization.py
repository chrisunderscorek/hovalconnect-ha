"""Local labels that can be configured independently from Home Assistant."""
from __future__ import annotations

from collections.abc import Mapping

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_LANGUAGE,
    DOMAIN,
    LANGUAGE_DE,
    LANGUAGE_EN,
    LANGUAGE_SYSTEM,
    MANUFACTURER,
)

LANGUAGE_LABELS = {
    LANGUAGE_SYSTEM: "System",
    LANGUAGE_DE: "Deutsch",
    LANGUAGE_EN: "English",
}

SUPPORTED_LANGUAGES = tuple(LANGUAGE_LABELS)

ENTITY_NAMES: dict[str, dict[str, str]] = {
    LANGUAGE_DE: {
        "hk_circuit_temp_actual": "Raumtemperatur Ist",
        "hk_circuit_temp_target": "Raumtemperatur Soll",
        "ww_circuit_temp_actual": "Ist-Temperatur SF1",
        "flow_temp_actual": "Vorlauftemperatur Ist",
        "flow_temp_target": "Vorlauftemperatur Soll",
        "room_temp_actual": "Raumtemperatur Ist",
        "room_temp_target": "Raumtemperatur Soll",
        "outside_temperature": "Außentemperatur",
        "generator_temp_actual": "Wärmeerzeuger-Ist",
        "generator_temp_target": "Wärmeerzeuger Soll",
        "return_temperature": "Rücklauftemperatur",
        "modulation": "Modulation",
        "operating_hours": "Betriebsstunden",
        "operation_cycles": "Schaltzyklen",
        "operating_hours_over_50": "Betriebsstunden > 50%",
        "error_code": "Fehlercode",
        "ww_temp_sf1_actual": "Ist-Temperatur SF1",
        "ww_temp_sf2_actual": "Ist-Temperatur SF2",
        "hot_water_temp_target": "Soll-Temperatur",
        "heat_amount": "Wärmemenge Heizen",
        "total_electrical_energy": "Elektrische Gesamtenergie",
        "hk_status": "Status",
        "ww_status": "Status",
        "bl_status": "Status Wärmeerzeuger",
        "hk_active_program": "Aktives Programm",
        "ww_active_program": "Aktives Programm",
    },
    LANGUAGE_EN: {
        "hk_circuit_temp_actual": "Room temperature actual",
        "hk_circuit_temp_target": "Room temperature set",
        "ww_circuit_temp_actual": "Actual temperature SF1",
        "flow_temp_actual": "Flow temperature actual",
        "flow_temp_target": "Flow temperature set",
        "room_temp_actual": "Room temperature actual",
        "room_temp_target": "Room temperature set",
        "outside_temperature": "Outdoor temperature",
        "generator_temp_actual": "Heat generator actual",
        "generator_temp_target": "Heat generator set",
        "return_temperature": "Return temperature",
        "modulation": "Modulation",
        "operating_hours": "Operating hours",
        "operation_cycles": "Switching cycles",
        "operating_hours_over_50": "Operating hours > 50%",
        "error_code": "Error code",
        "ww_temp_sf1_actual": "Actual temperature SF1",
        "ww_temp_sf2_actual": "Actual temperature SF2",
        "hot_water_temp_target": "Setpoint temperature",
        "heat_amount": "Heat amount",
        "total_electrical_energy": "Total electrical energy",
        "hk_status": "Status",
        "ww_status": "Status",
        "bl_status": "Status heat generator",
        "hk_active_program": "Active program",
        "ww_active_program": "Active program",
    },
}

PROGRAM_NAMES: dict[str, dict[str, str]] = {
    LANGUAGE_DE: {
        "week1": "Wochenprogramm 1",
        "week2": "Wochenprogramm 2",
        "constant": "Konstant",
        "ecoMode": "Eco-Modus",
    },
    LANGUAGE_EN: {
        "week1": "Weekly Program 1",
        "week2": "Weekly Program 2",
        "constant": "Constant",
        "ecoMode": "Eco Mode",
    },
}

PROGRAM_SELECT_SUFFIX = {
    LANGUAGE_DE: "Programm",
    LANGUAGE_EN: "Program",
}


def configured_language(entry: ConfigEntry) -> str:
    """Return the language explicitly configured for this integration."""
    language = entry.options.get(CONF_LANGUAGE, entry.data.get(CONF_LANGUAGE, LANGUAGE_SYSTEM))
    return language if language in SUPPORTED_LANGUAGES else LANGUAGE_SYSTEM


def effective_language(entry: ConfigEntry, hass_language: str | None = None) -> str:
    """Resolve system language to the closest supported local label set."""
    language = configured_language(entry)
    if language != LANGUAGE_SYSTEM:
        return language
    if hass_language and hass_language.lower().startswith("de"):
        return LANGUAGE_DE
    return LANGUAGE_EN


def apply_entity_name(entity, entry: ConfigEntry, translation_key: str) -> None:
    """Use HA translations in system mode, otherwise pin the configured language.

    Home Assistant entity translations always follow the global frontend
    language. The HovalConnect app shows its own German/English labels, so a
    per-integration language option needs explicit entity names instead.
    """
    language = configured_language(entry)
    if language == LANGUAGE_SYSTEM:
        entity._attr_translation_key = translation_key
        return

    entity._attr_name = ENTITY_NAMES.get(language, {}).get(translation_key, translation_key)


def program_names(entry: ConfigEntry, hass_language: str | None = None) -> Mapping[str, str]:
    """Return localized program labels for select options."""
    return PROGRAM_NAMES[effective_language(entry, hass_language)]


def program_select_suffix(entry: ConfigEntry, hass_language: str | None = None) -> str:
    """Return the localized suffix for the program select entity name."""
    return PROGRAM_SELECT_SUFFIX[effective_language(entry, hass_language)]


def device_info(coordinator, plant_id: str) -> dict:
    """Build device metadata from the API instead of a hard-coded model name."""
    model = None
    for circuit in coordinator.data.get("circuits", []):
        if circuit.get("type") == "BL" and circuit.get("name"):
            model = circuit["name"]
            break

    name = f"{MANUFACTURER} {model}" if model else MANUFACTURER
    info = {
        "identifiers": {(DOMAIN, plant_id)},
        "name": name,
        "manufacturer": MANUFACTURER,
    }
    if model:
        info["model"] = model
    return info
