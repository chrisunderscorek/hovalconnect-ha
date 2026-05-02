"""Home Assistant device metadata for Hoval plant and circuit devices."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_PLANT_NAME,
    DOMAIN,
    LANGUAGE_DE,
    LANGUAGE_EN,
    MANUFACTURER,
)
from .localization import effective_language

DEVICE_MODEL_LABELS = {
    LANGUAGE_DE: {
        "plant": "Anlage",
        "BL": "W\u00e4rmepumpe",
        "HK": "Heizkreis",
        "WW": "Warmwasser",
        "HV": "L\u00fcftung",
        "GW": "Gateway",
    },
    LANGUAGE_EN: {
        "plant": "Plant",
        "BL": "Heat pump",
        "HK": "Heating circuit",
        "WW": "Hot water",
        "HV": "Ventilation",
        "GW": "Gateway",
    },
}


def plant_device_identifier(plant_id: str) -> tuple[str, str]:
    """Return the stable Home Assistant identifier for a Hoval plant."""
    return (DOMAIN, plant_id)


def circuit_device_identifier(plant_id: str, circuit_path: str) -> tuple[str, str]:
    """Return the stable Home Assistant identifier for a Hoval circuit."""
    return (DOMAIN, f"{plant_id}:circuit:{circuit_path}")


def _prefixed_hoval_name(name: str) -> str:
    name = str(name).strip()
    if name.lower().startswith(MANUFACTURER.lower()):
        return name
    return f"{MANUFACTURER} {name}" if name else MANUFACTURER


def _plant_name(entry: ConfigEntry, plant_id: str) -> str:
    stored_name = entry.data.get(CONF_PLANT_NAME)
    if stored_name:
        return str(stored_name).strip()

    title = entry.title or ""
    for separator in ("\u2013", "-"):
        prefix = f"{MANUFACTURER} {separator} "
        if title.startswith(prefix):
            candidate = title.removeprefix(prefix).strip()
            if candidate:
                return candidate

    return plant_id


def _circuit_for_path(coordinator, circuit_path: str) -> dict:
    data = coordinator.data or {}
    for circuit in data.get("circuits", []):
        if circuit.get("path") == circuit_path:
            return circuit
    return {}


def circuit_type_label(entry: ConfigEntry, key: str, hass_language: str | None = None) -> str:
    """Return the localized display label for a circuit type."""
    language = effective_language(entry, hass_language)
    labels = DEVICE_MODEL_LABELS.get(language, DEVICE_MODEL_LABELS[LANGUAGE_EN])
    return labels.get(key, f"Circuit {key}" if key else "Circuit")


def plant_device_info(
    entry: ConfigEntry,
    plant_id: str,
    hass_language: str | None = None,
) -> dict:
    """Build device metadata for the whole Hoval plant.

    The plant is the parent device. Circuit entities should not reuse this
    device, because HA can only group by Anlage/WP/HK/WW if every circuit gets
    its own child device.
    """
    return {
        "identifiers": {plant_device_identifier(plant_id)},
        "name": _prefixed_hoval_name(_plant_name(entry, plant_id)),
        "manufacturer": MANUFACTURER,
        "model": circuit_type_label(entry, "plant", hass_language),
    }


def circuit_device_info(
    coordinator,
    entry: ConfigEntry,
    plant_id: str,
    circuit_path: str,
    hass_language: str | None = None,
) -> dict:
    """Build device metadata for one Hoval circuit child device."""
    circuit = _circuit_for_path(coordinator, circuit_path)
    circuit_type = circuit.get("type", "")
    if circuit:
        fallback_name = circuit_type_label(entry, circuit_type, hass_language)
        circuit_name = str(circuit.get("name") or fallback_name).strip()
    else:
        circuit_name = circuit_path

    return {
        "identifiers": {circuit_device_identifier(plant_id, circuit_path)},
        "name": _prefixed_hoval_name(circuit_name),
        "manufacturer": MANUFACTURER,
        "model": circuit_type_label(entry, circuit_type, hass_language),
        "via_device": plant_device_identifier(plant_id),
    }
