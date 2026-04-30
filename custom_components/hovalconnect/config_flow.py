"""Config flow for Hoval Connect."""
from __future__ import annotations
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import HovalAuthError, HovalAPIError, HovalConnectAPI
from .const import (
    CONF_EMAIL,
    CONF_LANGUAGE,
    CONF_PASSWORD,
    CONF_PLANT_ID,
    CONF_STORE_PASSWORD,
    DOMAIN,
    LANGUAGE_SYSTEM,
    MANUFACTURER,
)
from .localization import LANGUAGE_LABELS

_LOGGER = logging.getLogger(__name__)

PASSWORD_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)
LANGUAGE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            {"value": value, "label": label}
            for value, label in LANGUAGE_LABELS.items()
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)


def _credentials_schema(
    email: str | None = None,
    store_password: bool = False,
    language: str = LANGUAGE_SYSTEM,
    include_language: bool = True,
) -> vol.Schema:
    email_field = vol.Required(CONF_EMAIL, default=email) if email else vol.Required(CONF_EMAIL)
    fields = {
        email_field: str,
        vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
        vol.Optional(CONF_STORE_PASSWORD, default=store_password): bool,
    }
    if include_language:
        fields[vol.Optional(CONF_LANGUAGE, default=language)] = LANGUAGE_SELECTOR
    return vol.Schema(fields)


def _options_schema(language: str = LANGUAGE_SYSTEM) -> vol.Schema:
    return vol.Schema({vol.Optional(CONF_LANGUAGE, default=language): LANGUAGE_SELECTOR})


class HovalConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._plants = []
        self._tokens = {}
        self._language = LANGUAGE_SYSTEM

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            store_password = user_input.get(CONF_STORE_PASSWORD, False)
            self._language = user_input.get(CONF_LANGUAGE, LANGUAGE_SYSTEM)
            session = async_get_clientsession(self.hass)
            api = HovalConnectAPI(
                session=session,
                email=email,
                password=password,
            )
            try:
                self._plants = await api.get_plants()
                self._tokens = {
                    CONF_STORE_PASSWORD: store_password,
                    **api.auth_data(),
                }
                if store_password:
                    self._tokens[CONF_EMAIL] = email
                    self._tokens[CONF_PASSWORD] = password
            except HovalAuthError as err:
                _LOGGER.warning("Setup auth error: %s", err)
                errors["base"] = "invalid_auth"
            except HovalAPIError as err:
                _LOGGER.error("Setup API error: %s", err)
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.error("Setup error: %s", err)
                errors["base"] = "cannot_connect"

            if not errors:
                if not self._plants:
                    return self.async_abort(reason="no_plants")
                return await self.async_step_plant()

        return self.async_show_form(
            step_id="user",
            data_schema=_credentials_schema(),
            errors=errors,
        )

    async def async_step_plant(self, user_input=None):
        options = {
            p.get("plantExternalId", str(i)): p.get("description", f"Plant {i+1}")
            for i, p in enumerate(self._plants)
        }
        if user_input is not None:
            plant_id = user_input[CONF_PLANT_ID]
            await self.async_set_unique_id(f"hoval_{plant_id}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"{MANUFACTURER} – {options.get(plant_id, plant_id)}",
                data={CONF_PLANT_ID: plant_id, **self._tokens},
                options={CONF_LANGUAGE: self._language},
            )
        return self.async_show_form(
            step_id="plant",
            data_schema=vol.Schema({vol.Required(CONF_PLANT_ID): vol.In(options)}),
        )

    async def async_step_reauth(self, entry_data=None):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            store_password = user_input.get(CONF_STORE_PASSWORD, False)
            session = async_get_clientsession(self.hass)
            api = HovalConnectAPI(
                session=session,
                email=email,
                password=password,
            )
            try:
                await api.get_plants()
                reauth_entry = self._get_reauth_entry()
                new_data = {
                    **reauth_entry.data,
                    CONF_STORE_PASSWORD: store_password,
                    **api.auth_data(),
                }
                if store_password:
                    new_data[CONF_EMAIL] = email
                    new_data[CONF_PASSWORD] = password
                else:
                    new_data.pop(CONF_EMAIL, None)
                    new_data.pop(CONF_PASSWORD, None)
                self.hass.config_entries.async_update_entry(
                    reauth_entry,
                    data=new_data,
                )
                await self.hass.config_entries.async_reload(reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            except HovalAuthError as err:
                _LOGGER.warning("Reauth auth error: %s", err)
                errors["base"] = "invalid_auth"
            except HovalAPIError as err:
                _LOGGER.error("Reauth API error: %s", err)
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.error("Reauth error: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_credentials_schema(
                email=self._get_reauth_entry().data.get(CONF_EMAIL),
                store_password=self._get_reauth_entry().data.get(CONF_STORE_PASSWORD, False),
                language=self._get_reauth_entry().options.get(CONF_LANGUAGE, LANGUAGE_SYSTEM),
                include_language=False,
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return HovalConnectOptionsFlow(config_entry)


class HovalConnectOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(
                self._config_entry.options.get(CONF_LANGUAGE, LANGUAGE_SYSTEM)
            ),
        )
