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
        "hk_circuit_temp_actual": "Raumtemp. Ist",
        "hk_circuit_temp_target": "Raumtemp. Soll",
        "ww_circuit_temp_actual": "Ist-Temp. WW",
        "flow_temp_actual": "Vorlauftemp. Ist",
        "flow_temp_target": "Vorlauftemp. Soll",
        "room_temp_actual": "Raumtemp. Ist",
        "room_temp_target": "Raumtemp. Soll",
        "outside_temperature": "Außentemp.",
        "generator_temp_actual": "Wärmeerzeuger-Ist",
        "generator_temp_target": "Wärmeerzeuger Soll",
        "return_temperature": "Rücklauftemp.",
        "modulation": "Modulation",
        "operating_hours": "Betriebsstunden",
        "operation_cycles": "Schaltzyklen",
        "operating_hours_over_50": "Betriebsstunden > 50%",
        "error_code": "Betriebsstatus",
        "plant_status": "Betriebsstatus",
        "storage_temp_actual": "Ist-Temp. WW",
        "ww_temp_sf1_actual": "Ist-Temp. SF1",
        "ww_temp_sf2_actual": "Ist-Temp. SF2",
        "hot_water_temp_target": "Soll-Temp.",
        "heat_amount": "Wärmemenge Heizen",
        "total_electrical_energy": "Elektrische Gesamtenergie",
        "hk_status": "Status Heizkreis",
        "ww_status": "Status Warmwasser",
        "bl_status": "Status Wärmeerzeuger",
        "hk_active_program": "Akt. Heizkreisprog.",
        "ww_active_program": "Akt. Warmwasserprog.",
    },
    LANGUAGE_EN: {
        "hk_circuit_temp_actual": "Room temp. actual",
        "hk_circuit_temp_target": "Room temp. set",
        "ww_circuit_temp_actual": "Hot water temp. actual",
        "flow_temp_actual": "Flow temp. actual",
        "flow_temp_target": "Flow temp. set",
        "room_temp_actual": "Room temp. actual",
        "room_temp_target": "Room temp. set",
        "outside_temperature": "Outdoor temp.",
        "generator_temp_actual": "Heat generator actual",
        "generator_temp_target": "Heat generator set",
        "return_temperature": "Return temp.",
        "modulation": "Modulation",
        "operating_hours": "Operating hours",
        "operation_cycles": "Switching cycles",
        "operating_hours_over_50": "Operating hours > 50%",
        "error_code": "Operating status",
        "plant_status": "Operating status",
        "storage_temp_actual": "Hot water temp. actual",
        "ww_temp_sf1_actual": "Actual temp. SF1",
        "ww_temp_sf2_actual": "Actual temp. SF2",
        "hot_water_temp_target": "Setpoint temp.",
        "heat_amount": "Heat amount",
        "total_electrical_energy": "Total electrical energy",
        "hk_status": "Heating circuit status",
        "ww_status": "Hot water status",
        "bl_status": "Heat generator status",
        "hk_active_program": "Heating circuit prog.",
        "ww_active_program": "Hot water prog.",
    },
}

PROGRAM_NAMES: dict[str, dict[str, str]] = {
    LANGUAGE_DE: {
        "week1": "Wochenprog. 1",
        "week2": "Wochenprog. 2",
        "constant": "Konstant",
        "ecoMode": "Eco-Modus",
    },
    LANGUAGE_EN: {
        "week1": "Weekly Prog. 1",
        "week2": "Weekly Prog. 2",
        "constant": "Constant",
        "ecoMode": "Eco Mode",
    },
}

PROGRAM_SELECT_SUFFIX = {
    LANGUAGE_DE: "Prog.",
    LANGUAGE_EN: "Prog.",
}

STATUS_VALUES = {
    LANGUAGE_DE: {
        "heating": "Heizen",
        "cooling": "Kühlen",
        "charging": "Laden",
        "off": "Abgeschaltet",
        "standby": "Bereit",
        "error": "Störung",
    },
    LANGUAGE_EN: {
        "heating": "Heating",
        "cooling": "Cooling",
        "charging": "Charging",
        "off": "Switched off",
        "standby": "Standby",
        "error": "Error",
    },
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


def active_program_value(
    entry: ConfigEntry,
    active_program: str | None,
    week_program: str | None,
    day_program: str | None,
    hass_language: str | None = None,
) -> str | None:
    """Return the user-facing active program value for a program sensor.

    The API key (`week1`, `week2`, ...) is stable but not useful in Home
    Assistant. The circuit payload also carries the HovalConnect labels for the
    active week and day programs, so the sensor state should expose those names.
    """
    if week_program and day_program:
        return f"{week_program} - {day_program}"
    if week_program:
        return week_program
    if not active_program:
        return None
    return program_names(entry, hass_language).get(active_program, active_program)


def localized_status_value(
    entry: ConfigEntry,
    raw_status: str | None,
    hass_language: str | None = None,
) -> str | None:
    """Return a localized circuit status while keeping unknown API values raw."""
    if raw_status is None:
        return None

    status_key = str(raw_status).strip().lower()
    if not status_key:
        return None
    return STATUS_VALUES[effective_language(entry, hass_language)].get(status_key, raw_status)


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
