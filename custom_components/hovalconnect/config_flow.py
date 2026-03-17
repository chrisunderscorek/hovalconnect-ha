"""Config flow for Hoval Connect."""
from __future__ import annotations
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import HovalConnectAPI
from .const import CONF_PLANT_ID, DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

class HovalConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._plants = []
        self._tokens = {}

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = HovalConnectAPI(
                session=session,
                access_token=user_input["access_token"].strip(),
                refresh_token=user_input["refresh_token"].strip(),
            )
            try:
                self._plants = await api.get_plants()
                self._tokens = {"access_token": user_input["access_token"].strip(), "refresh_token": user_input["refresh_token"].strip()}
            except Exception as err:
                _LOGGER.error("Setup error: %s", err)
                errors["base"] = "cannot_connect"

            if not errors:
                if not self._plants:
                    return self.async_abort(reason="no_plants")
                return await self.async_step_plant()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("access_token"): str, vol.Required("refresh_token"): str}),
            errors=errors,
        )

    async def async_step_plant(self, user_input=None):
        options = {p.get("plantExternalId", str(i)): p.get("description", f"Plant {i+1}") for i, p in enumerate(self._plants)}
        if user_input is not None:
            plant_id = user_input[CONF_PLANT_ID]
            await self.async_set_unique_id(f"hoval_{plant_id}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{MANUFACTURER} – {options.get(plant_id, plant_id)}",
                data={CONF_PLANT_ID: plant_id, **self._tokens},
            )
        return self.async_show_form(
            step_id="plant",
            data_schema=vol.Schema({vol.Required(CONF_PLANT_ID): vol.In(options)}),
        )


class HovalConnectReauthFlow(config_entries.ConfigEntryBaseFlow):
    """Re-authentication flow — shown when refresh token expires."""

    async def async_step_reauth(self, user_input=None):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = HovalConnectAPI(
                session=session,
                access_token=user_input["access_token"].strip(),
                refresh_token=user_input["refresh_token"].strip(),
            )
            try:
                await api.get_plants()
                # Update existing entry with new tokens
                self.hass.config_entries.async_update_entry(
                    self._get_reauth_entry(),
                    data={
                        **self._get_reauth_entry().data,
                        "access_token": user_input["access_token"].strip(),
                        "refresh_token": user_input["refresh_token"].strip(),
                    },
                )
                await self.hass.config_entries.async_reload(self._get_reauth_entry().entry_id)
                return self.async_abort(reason="reauth_successful")
            except Exception as err:
                _LOGGER.error("Reauth error: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required("access_token"): str,
                vol.Required("refresh_token"): str,
            }),
            errors=errors,
        )
