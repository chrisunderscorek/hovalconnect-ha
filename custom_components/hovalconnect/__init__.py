"""Hoval Connect Integration."""
from __future__ import annotations
import asyncio
import logging
import time
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import HovalAuthError, HovalAPIError, HovalConnectAPI
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PLANT_ID,
    CONF_TOKEN_EXPIRES_AT,
    CONF_TOKEN_ISSUED_AT,
    CONF_TOKEN_RENEW_AFTER,
    DOMAIN,
    UPDATE_INTERVAL_SECONDS,
)
from .devices import circuit_device_info, plant_device_info

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.SELECT]
LIVE_VALUE_CIRCUIT_TYPES = {"HK", "BL", "WW"}


def _register_devices_and_migrate_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: DataUpdateCoordinator,
    plant_id: str,
) -> None:
    """Register plant/circuit devices and move existing entities to circuits.

    Home Assistant keeps the existing device assignment for already registered
    entities. The integration therefore has to migrate old single-device entity
    registry entries explicitly when introducing the circuit device hierarchy.

    TODO: Keep this compatibility migration while users can still upgrade from
    <=0.2.1. It is idempotent for new installs and can be removed after a few
    releases once the circuit device hierarchy is the normal baseline.
    """
    device_reg = dr.async_get(hass)
    device_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        **plant_device_info(entry, plant_id, hass.config.language),
    )

    circuit_device_ids = {}
    for circuit in (coordinator.data or {}).get("circuits", []):
        path = circuit.get("path")
        if not path:
            continue
        device = device_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            **circuit_device_info(
                coordinator,
                entry,
                plant_id,
                path,
                hass.config.language,
            ),
        )
        circuit_device_ids[path] = device.id

    if not circuit_device_ids:
        return

    entity_reg = er.async_get(hass)
    migrated_entities = 0
    for entity_entry in er.async_entries_for_config_entry(entity_reg, entry.entry_id):
        if entity_entry.platform != DOMAIN or not entity_entry.unique_id:
            continue

        for path, device_id in circuit_device_ids.items():
            if entity_entry.unique_id.startswith(f"hoval_{plant_id}_{path}_"):
                if entity_entry.device_id != device_id:
                    entity_reg.async_update_entity(entity_entry.entity_id, device_id=device_id)
                    migrated_entities += 1
                break

    if migrated_entities:
        _LOGGER.info(
            "Migrated %s Hoval Connect entities from the legacy plant device "
            "to circuit devices",
            migrated_entities,
        )


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    current_options = dict(entry.options)
    if runtime and runtime.get("last_options") == current_options:
        # Token persistence updates the config entry data. That must not reload
        # the integration, because reloads briefly drive entities unavailable.
        _LOGGER.debug("Skipping Hoval Connect reload for data-only config entry update")
        return
    if runtime is not None:
        runtime["last_options"] = current_options
    await hass.config_entries.async_reload(entry.entry_id)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api = HovalConnectAPI(
        session=session,
        access_token=entry.data.get("access_token"),
        refresh_token=entry.data.get("refresh_token"),
        token_issued_at=entry.data.get(CONF_TOKEN_ISSUED_AT),
        token_expires_at=entry.data.get(CONF_TOKEN_EXPIRES_AT),
        token_renew_after=entry.data.get(CONF_TOKEN_RENEW_AFTER),
        email=entry.data.get(CONF_EMAIL),
        password=entry.data.get(CONF_PASSWORD),
    )
    api.set_request_retry_window(UPDATE_INTERVAL_SECONDS / 2)
    await api.async_update_frontend_app_version(reason="startup", force=True)
    plant_id = entry.data[CONF_PLANT_ID]

    async def _update():
        started = time.monotonic()
        previous = coordinator.data or {}
        try:
            try:
                circuits = await api.get_circuits(plant_id)
            except HovalAuthError:
                raise
            except Exception as circuits_err:
                if previous:
                    _LOGGER.warning(
                        "Circuits fetch failed for %s; keeping previous coordinator data: %s",
                        plant_id,
                        circuits_err,
                    )
                    return {
                        **previous,
                        "fetch_stats": {
                            **previous.get("fetch_stats", {}),
                            "stale": True,
                            "stale_reason": f"circuits fetch failed: {circuits_err}",
                            "duration_ms": round((time.monotonic() - started) * 1000),
                            "reused_previous_update": True,
                        },
                    }
                raise

            previous_live_values = previous.get("live_values", {})
            previous_business_details = previous.get("business_details", {})
            live_values = {}
            business_details = {}
            reused_live_values = []
            reused_business_details = []
            live_value_errors = {}
            business_detail_errors = {}

            async def _fetch_circuit_data(c):
                path = c.get("path", "")
                ctype = c.get("type", "")
                result = {
                    "path": path,
                    "ctype": ctype,
                    "live_values": None,
                    "business_detail": None,
                    "reused_live": False,
                    "reused_business": False,
                    "live_error": None,
                    "business_error": None,
                }
                if not path or not ctype:
                    return result

                if ctype in LIVE_VALUE_CIRCUIT_TYPES:
                    try:
                        lv = await api.get_live_values(plant_id, path, ctype)
                        if lv:
                            result["live_values"] = lv
                        elif path in previous_live_values:
                            result["live_values"] = previous_live_values[path]
                            result["reused_live"] = True
                            _LOGGER.warning(
                                "No live values for %s/%s; keeping previous values",
                                path,
                                ctype,
                            )
                        else:
                            _LOGGER.debug("No live values for %s/%s", path, ctype)
                    except Exception as lv_err:
                        result["live_error"] = str(lv_err)
                        if path in previous_live_values:
                            result["live_values"] = previous_live_values[path]
                            result["reused_live"] = True
                            _LOGGER.warning(
                                "Live values error for %s/%s; keeping previous values: %s",
                                path,
                                ctype,
                                lv_err,
                            )
                        else:
                            _LOGGER.warning(
                                "Live values error for %s/%s without previous values: %s",
                                path,
                                ctype,
                                lv_err,
                            )

                # The WFA operating status code is not always part of the
                # live-values response. The read-only business detail tree
                # exposes the internal status datapoint (*.2053), which we
                # use as a fallback for the localized Betriebsstatus sensor.
                if ctype == "BL":
                    try:
                        detail = await api.get_business_circuit_detail(plant_id, path)
                        if detail:
                            result["business_detail"] = detail
                        elif path in previous_business_details:
                            result["business_detail"] = previous_business_details[path]
                            result["reused_business"] = True
                    except Exception as detail_err:
                        result["business_error"] = str(detail_err)
                        if path in previous_business_details:
                            result["business_detail"] = previous_business_details[path]
                            result["reused_business"] = True
                            _LOGGER.warning(
                                "Business detail error for %s/%s; keeping previous values: %s",
                                path,
                                ctype,
                                detail_err,
                            )
                        else:
                            _LOGGER.warning(
                                "Business detail error for %s/%s without previous values: %s",
                                path,
                                ctype,
                                detail_err,
                            )
                return result

            results = await asyncio.gather(*(_fetch_circuit_data(c) for c in circuits))
            for result in results:
                path = result["path"]
                if not path:
                    continue
                if result["live_values"] is not None:
                    live_values[path] = result["live_values"]
                    if result["reused_live"]:
                        reused_live_values.append(f"{path}/{result['ctype']}")
                if result["business_detail"] is not None:
                    business_details[path] = result["business_detail"]
                    if result["reused_business"]:
                        reused_business_details.append(f"{path}/{result['ctype']}")
                if result["live_error"]:
                    live_value_errors[f"{path}/{result['ctype']}"] = result["live_error"]
                if result["business_error"]:
                    business_detail_errors[f"{path}/{result['ctype']}"] = result["business_error"]

            return {
                "circuits": circuits,
                "live_values": live_values,
                "business_details": business_details,
                "plant_id": plant_id,
                "fetch_stats": {
                    "stale": bool(reused_live_values or reused_business_details),
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    "reused_live_values": reused_live_values,
                    "reused_business_details": reused_business_details,
                    "live_value_errors": live_value_errors,
                    "business_detail_errors": business_detail_errors,
                },
            }
        except HovalAuthError as err:
            entry.async_start_reauth(hass)
            raise UpdateFailed(f"Auth expired, re-authentication required: {err}") from err
        except (HovalAPIError, Exception) as err:
            raise UpdateFailed(str(err)) from err

    # Save refreshed tokens back to config entry for persistence
    def _save_tokens(auth_data: dict) -> None:
        new_data = {**entry.data, **auth_data}
        hass.config_entries.async_update_entry(entry, data=new_data)
        _LOGGER.debug("Tokens refreshed and saved to config entry")

    api.set_token_refresh_callback(_save_tokens)

    coordinator = DataUpdateCoordinator(
        hass, _LOGGER,
        name=f"hovalconnect_{plant_id}",
        update_method=_update,
        update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
    )
    await coordinator.async_config_entry_first_refresh()
    _register_devices_and_migrate_entities(hass, entry, coordinator, plant_id)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "plant_id": plant_id,
        "last_options": dict(entry.options),
    }
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False
