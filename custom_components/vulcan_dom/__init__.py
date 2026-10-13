"""Integracja eduVULCAN (nieoficjalna) dla Home Assistant."""

from __future__ import annotations

import logging
from datetime import date

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import CONF_CREDENTIAL, CONF_WRITE_LIMIT, DEFAULT_WRITE_LIMIT, DOMAIN, PLATFORMS
from .coordinator import VulcanCoordinator
from .vulcan_client import ApiError, Credential, TransportError, VulcanApi

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ATTR_PUPIL = "pupil"
BASE_SCHEMA = {vol.Optional(ATTR_PUPIL): cv.string}

SCHEMA_SEND = vol.Schema({
    **BASE_SCHEMA,
    vol.Required("recipient"): cv.string,
    vol.Required("subject"): vol.All(cv.string, vol.Length(min=1, max=200)),
    vol.Required("message"): vol.All(cv.string, vol.Length(min=1, max=10000)),
})
SCHEMA_JUSTIFY = vol.Schema({
    **BASE_SCHEMA,
    vol.Required("date"): cv.date,
    vol.Optional("lessons"): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Required("reason"): vol.All(cv.string, vol.Length(min=3, max=500)),
})
SCHEMA_RECIPIENTS = vol.Schema({**BASE_SCHEMA, vol.Optional("search"): cv.string})
SCHEMA_REFRESH = vol.Schema({})

type VulcanConfigEntry = ConfigEntry[VulcanCoordinator]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    _register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: VulcanConfigEntry) -> bool:
    credential = Credential.from_dict(entry.data[CONF_CREDENTIAL])
    api = VulcanApi(credential, async_get_clientsession(hass))
    coordinator = VulcanCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    # Skrzynka poza setupem: pierwsze odświeżenie dało już plan, oceny i sprawdziany,
    # więc encje mają dane. Wiadomości dociągamy w tle, żeby wolna albo niedostępna
    # skrzynka nie przedłużała startu Home Assistanta.
    coordinator.enable_messages()
    entry.async_create_background_task(
        hass, coordinator.async_request_refresh(), f"{DOMAIN}_wiadomosci_po_starcie"
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload_on_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VulcanConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _reload_on_options(hass: HomeAssistant, entry: VulcanConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


# --- usługi ---------------------------------------------------------------------


class _WriteLimiter:
    """Prosty dzienny limit zapisów na wpis konfiguracji (ochrona przed pętlą w automatyzacji)."""

    def __init__(self) -> None:
        self.day: date | None = None
        self.count: dict[str, int] = {}

    def take(self, entry: ConfigEntry) -> None:
        today = dt_util.now().date()
        if self.day != today:
            self.day, self.count = today, {}
        limit = entry.options.get(CONF_WRITE_LIMIT, DEFAULT_WRITE_LIMIT)
        used = self.count.get(entry.entry_id, 0)
        if used >= limit:
            raise ServiceValidationError(f"dzienny limit zapisów ({limit}) wyczerpany")
        self.count[entry.entry_id] = used + 1


def _target(hass: HomeAssistant, call: ServiceCall) -> tuple[VulcanCoordinator, dict]:
    """Wybiera konto i ucznia po fragmencie imienia/nazwiska (lub jedynego)."""
    wanted = (call.data.get(ATTR_PUPIL) or "").lower()
    matches = []
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        coord: VulcanCoordinator = entry.runtime_data
        for acc in coord.accounts:
            p = acc["Pupil"]
            name = f"{p.get('FirstName', '')} {p.get('Surname', '')}".lower()
            if not wanted or wanted in name or wanted == str(p.get("LoginId")):
                matches.append((coord, acc))
    if len(matches) != 1:
        raise ServiceValidationError(
            "nie znaleziono ucznia" if not matches else "kilku uczniów pasuje — podaj 'pupil'"
        )
    return matches[0]


def _register_services(hass: HomeAssistant) -> None:
    limiter = _WriteLimiter()

    async def recipients(call: ServiceCall) -> ServiceResponse:
        coord, acc = _target(hass, call)
        box = acc.get("MessageBox") or {}
        if not box:
            raise ServiceValidationError("konto ucznia nie ma skrzynki wiadomości")
        try:
            book = await coord.api.addressbook(acc["Unit"]["RestURL"], acc["Pupil"]["Id"], box["GlobalKey"])
        except (ApiError, TransportError) as err:
            raise HomeAssistantError(str(err)) from err
        search = (call.data.get("search") or "").lower()
        names = [r.get("Name") for r in book or [] if search in (r.get("Name") or "").lower()]
        return {"recipients": sorted(n for n in names if n)}

    async def send_message(call: ServiceCall) -> ServiceResponse:
        coord, acc = _target(hass, call)
        box = acc.get("MessageBox") or {}
        if not box:
            raise ServiceValidationError("konto ucznia nie ma skrzynki wiadomości")
        rest, pid = acc["Unit"]["RestURL"], acc["Pupil"]["Id"]
        try:
            book = await coord.api.addressbook(rest, pid, box["GlobalKey"])
        except (ApiError, TransportError) as err:
            raise HomeAssistantError(str(err)) from err
        needle = call.data["recipient"].lower()
        found = [r for r in book or [] if needle in (r.get("Name") or "").lower()]
        if len(found) != 1:
            names = [r.get("Name") for r in found][:10]
            raise ServiceValidationError(f"adresat musi być jednoznaczny; pasuje {len(found)}: {names}")
        limiter.take(coord.config_entry)
        payload = coord.api.message_payload(
            box["GlobalKey"], box["Name"], found, call.data["subject"], call.data["message"]
        )
        try:
            await coord.api.send_message(rest, pid, payload)
        except (ApiError, TransportError) as err:
            raise HomeAssistantError(f"wysyłka nieudana: {err}") from err
        _LOGGER.info("wysłano wiadomość do %s (temat: %s)", found[0].get("Name"), call.data["subject"])
        return {"sent_to": found[0].get("Name")}

    async def justify(call: ServiceCall) -> ServiceResponse:
        coord, acc = _target(hass, call)
        rest, pid = acc["Unit"]["RestURL"], acc["Pupil"]["Id"]
        login = acc["Pupil"]["LoginId"]
        day: date = call.data["date"]
        wanted = set(call.data.get("lessons") or [])
        try:
            lessons = await coord.api.lessons(rest, pid, day, day)
        except (ApiError, TransportError) as err:
            raise HomeAssistantError(str(err)) from err
        targets = []
        for les in lessons or []:
            if not les.get("LessonClassId"):
                continue
            pos = (les.get("TimeSlot") or {}).get("Position")
            pres = les.get("PresenceType") or {}
            if wanted:
                if pos in wanted:
                    targets.append(les)
            elif pres.get("Absence") and not pres.get("AbsenceJustified"):
                targets.append(les)
        if not targets:
            raise ServiceValidationError(f"brak nieusprawiedliwionych nieobecności {day.isoformat()}")
        limiter.take(coord.config_entry)
        done = []
        for les in targets:
            payload = coord.api.justification_payload(pid, login, les["LessonClassId"], call.data["reason"])
            try:
                await coord.api.justify_lesson(rest, pid, payload)
            except (ApiError, TransportError) as err:
                raise HomeAssistantError(f"usprawiedliwienie nieudane po {len(done)} lekcjach: {err}") from err
            done.append((les.get("TimeSlot") or {}).get("Position"))
        await coord.async_request_refresh()
        return {"date": day.isoformat(), "lessons": done}

    async def refresh(call: ServiceCall) -> None:
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            entry.runtime_data.force_next = True
            await entry.runtime_data.async_refresh()

    hass.services.async_register(DOMAIN, "recipients", recipients, SCHEMA_RECIPIENTS,
                                 supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "send_message", send_message, SCHEMA_SEND,
                                 supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "justify_absence", justify, SCHEMA_JUSTIFY,
                                 supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "refresh", refresh, SCHEMA_REFRESH)
