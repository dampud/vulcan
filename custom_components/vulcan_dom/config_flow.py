"""Kreator: rejestracja HA jako urządzenia eduVULCAN z danych eduvulcan.pl/api/ap."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    CONF_AP_JSON,
    CONF_CREDENTIAL,
    CONF_QUIET_END,
    CONF_QUIET_START,
    CONF_SCAN_INTERVAL,
    CONF_TENANT,
    CONF_WRITE_LIMIT,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_START,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WRITE_LIMIT,
    DOMAIN,
)
from .vulcan_client import ApiError, Credential, TransportError, VulcanApi
from .vulcan_client.auth import ApDataError, parse_ap

_LOGGER = logging.getLogger(__name__)

AP_SCHEMA = vol.Schema({vol.Required(CONF_AP_JSON): TextSelector(TextSelectorConfig(multiline=True))})


class VulcanConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _register(self, raw: str) -> tuple[dict[str, Any] | None, dict[str, str]]:
        """Zwraca (dane wpisu, błędy). Dane z /api/ap nie są nigdzie zapisywane."""
        try:
            by_tenant = parse_ap(raw)
        except ApDataError as err:
            _LOGGER.debug("niepoprawne dane /api/ap: %s", err)
            return None, {"base": "invalid_ap"}
        if len(by_tenant) != 1:
            return None, {"base": "multiple_units"}
        tenant, tokens = next(iter(by_tenant.items()))
        credential: Credential = await self.hass.async_add_executor_job(Credential.create)
        api = VulcanApi(credential, async_get_clientsession(self.hass))
        try:
            await api.register_jwt(tokens, tenant)
            accounts = await api.accounts()
        except ApiError as err:
            _LOGGER.warning("rejestracja odrzucona: %s", err)
            return None, {"base": "rejected"}
        except TransportError as err:
            _LOGGER.warning("brak połączenia z eduVULCAN: %s", err)
            return None, {"base": "cannot_connect"}
        if not accounts:
            return None, {"base": "no_pupils"}
        names = [f"{a['Pupil'].get('FirstName', '')} {a['Pupil'].get('Surname', '')}".strip() for a in accounts]
        login_ids = sorted(str(a["Pupil"]["LoginId"]) for a in accounts)
        return {
            "unique_id": f"{tenant}-{'-'.join(login_ids)}",
            "title": "eduVULCAN – " + ", ".join(names),
            "data": {CONF_TENANT: tenant, CONF_CREDENTIAL: credential.to_dict()},
        }, {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            result, errors = await self._register(user_input[CONF_AP_JSON])
            if result:
                await self.async_set_unique_id(result["unique_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=result["title"], data=result["data"])
        return self.async_show_form(step_id="user", data_schema=AP_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            result, errors = await self._register(user_input[CONF_AP_JSON])
            if result:
                await self.async_set_unique_id(result["unique_id"])
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(self._get_reauth_entry(), data=result["data"])
        return self.async_show_form(step_id="reauth_confirm", data_schema=AP_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return VulcanOptionsFlow()


def _num(minimum: int, maximum: int, unit: str | None = None) -> NumberSelector:
    # unit_of_measurement musi być tekstem albo w ogóle go nie być — None wywraca selektor
    config = {"min": minimum, "max": maximum, "step": 1, "mode": NumberSelectorMode.BOX}
    if unit:
        config["unit_of_measurement"] = unit
    return NumberSelector(NumberSelectorConfig(**config))


class VulcanOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={k: int(v) for k, v in user_input.items()})
        o = self.config_entry.options
        schema = vol.Schema({
            vol.Required(CONF_SCAN_INTERVAL, default=o.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): _num(15, 180, "min"),
            vol.Required(CONF_QUIET_START, default=o.get(CONF_QUIET_START, DEFAULT_QUIET_START)): _num(0, 23, "h"),
            vol.Required(CONF_QUIET_END, default=o.get(CONF_QUIET_END, DEFAULT_QUIET_END)): _num(0, 23, "h"),
            vol.Required(CONF_WRITE_LIMIT, default=o.get(CONF_WRITE_LIMIT, DEFAULT_WRITE_LIMIT)): _num(0, 50),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
