"""Integracja eduVULCAN (nieoficjalna) dla Home Assistant."""

from __future__ import annotations

import logging
from datetime import date

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from . import model as m
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
SCHEMA_READ_MESSAGES = vol.Schema({
    **BASE_SCHEMA,
    vol.Optional("unread_only", default=False): cv.boolean,
    vol.Optional("search"): cv.string,
    vol.Optional("limit", default=10): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
})
SCHEMA_REFRESH = vol.Schema({})
SCHEMA_ATTENDANCE = vol.Schema({
    **BASE_SCHEMA,
    vol.Required("date_from"): cv.date,
    vol.Optional("date_to"): cv.date,
})
SCHEMA_SCHEDULE = vol.Schema({**BASE_SCHEMA, vol.Required("date"): cv.date})

type VulcanConfigEntry = ConfigEntry[VulcanCoordinator]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    _register_services(hass)
    return True


@callback
def _migrate_login_ids(hass: HomeAssistant, entry: ConfigEntry, coordinator: VulcanCoordinator) -> None:
    """Przenosi urządzenia i encje z klucza LoginId na Pupil.Id.

    Do 0.6.2 uczeń był rozpoznawany po LoginId, który rodzeństwo z jednego konta
    rodzica dzieli — przeżywało tylko jedno dziecko. Istniejące wpisy przepinamy na
    Pupil.Id, żeby po aktualizacji encje zachowały swoje entity_id i historię, zamiast
    pojawić się drugi raz z końcówką _2. Przy wspólnym LoginId stare wpisy należały do
    ostatniego ucznia na liście (tak działał dawny słownik), więc to jemu je oddajemy.
    """
    login_to_pupil: dict[str, str] = {}
    for acc in coordinator.accounts:
        pupil = acc["Pupil"]
        login_to_pupil[str(pupil["LoginId"])] = str(pupil["Id"])

    ent_reg = er.async_get(hass)
    for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        old, sep, key = ent.unique_id.partition("_")
        new = login_to_pupil.get(old)
        if not sep or new is None or new == old:
            continue
        new_uid = f"{new}_{key}"
        if ent_reg.async_get_entity_id(ent.domain, DOMAIN, new_uid) is None:
            ent_reg.async_update_entity(ent.entity_id, new_unique_id=new_uid)

    dev_reg = dr.async_get(hass)
    for dev in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        for domain, old in dev.identifiers:
            new = login_to_pupil.get(old) if domain == DOMAIN else None
            if new and new != old and dev_reg.async_get_device(identifiers={(DOMAIN, new)}) is None:
                dev_reg.async_update_device(dev.id, new_identifiers={(DOMAIN, new)})
                break


async def async_setup_entry(hass: HomeAssistant, entry: VulcanConfigEntry) -> bool:
    credential = Credential.from_dict(entry.data[CONF_CREDENTIAL])
    api = VulcanApi(credential, async_get_clientsession(hass))
    coordinator = VulcanCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    _migrate_login_ids(hass, entry, coordinator)
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
            if not wanted or wanted in name or wanted in (str(p.get("Id")), str(p.get("LoginId"))):
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
        # Świeży odczyt z serwera, nie stan koordynatora: między odświeżeniami ktoś mógł
        # już usprawiedliwić, a zapis jest nieodwracalny. Klasyfikację robi ten sam parser,
        # na którym stoi sensor — jedno miejsce decyduje, co jest do usprawiedliwienia.
        targets = []
        for les in lessons or []:
            att = m.parse_attendance(les)
            if att is None or att.lesson_class_id is None:
                continue
            if wanted:
                if att.position in wanted:
                    targets.append((les, att))
            elif att.to_justify:
                targets.append((les, att))
        if not targets:
            raise ServiceValidationError(
                f"brak nieusprawiedliwionych nieobecności {day.isoformat()}"
                if not wanted else
                f"lekcje {sorted(wanted)} z {day.isoformat()} nie mają wpisu frekwencji do usprawiedliwienia"
            )
        limiter.take(coord.config_entry)
        done = []
        for les, att in targets:
            payload = coord.api.justification_payload(pid, login, att.lesson_class_id, call.data["reason"])
            try:
                await coord.api.justify_lesson(rest, pid, payload)
            except (ApiError, TransportError) as err:
                raise HomeAssistantError(f"usprawiedliwienie nieudane po {len(done)} lekcjach: {err}") from err
            done.append(att.position)
        await coord.async_request_refresh()
        return {"date": day.isoformat(), "lessons": done}

    async def read_messages(call: ServiceCall) -> ServiceResponse:
        """Treść wiadomości ze skrzynki, na żądanie.

        Świadomie usługa, nie encja: treść korespondencji ze szkołą nie ma trafiać
        do bazy recordera przy każdej zmianie stanu ani do dziennika zdarzeń. Czytamy
        to, co koordynator ma już pobrane — bez dodatkowego ruchu do serwera.
        """
        coord, acc = _target(hass, call)
        pupil = (coord.data or {}).get(acc["Pupil"]["Id"])
        if pupil is None:
            raise HomeAssistantError("brak pobranych danych ucznia")
        szukaj = (call.data.get("search") or "").lower()
        wiadomosci = [
            msg for msg in pupil.messages
            if (not call.data["unread_only"] or not msg.read)
            and (not szukaj or szukaj in (msg.subject or "").lower() or szukaj in (msg.sender or "").lower())
        ]
        wiadomosci.sort(key=lambda x: (x.sent is not None, x.sent), reverse=True)
        return {
            "count": len(wiadomosci),
            "messages": [
                {
                    "key": msg.key,
                    "thread_key": msg.thread_key,
                    "sent": msg.sent.isoformat() if msg.sent else None,
                    "sender": msg.sender,
                    "subject": msg.subject,
                    "read": msg.read,
                    "content": msg.content,
                }
                for msg in wiadomosci[: call.data["limit"]]
            ],
        }

    async def attendance(call: ServiceCall) -> ServiceResponse:
        """Frekwencja z podanego zakresu dni, prosto z serwera.

        Odczyt na żądanie, niezależny od okna koordynatora — przydaje się, gdy trzeba
        zajrzeć w konkretny dzień albo sprawdzić, czy serwer w ogóle coś zwraca.
        `surowych_rekordow` to liczba rekordów przed parsowaniem: gdy jest zerowa,
        pusto jest po stronie serwera, a nie w klasyfikacji wpisów.
        """
        coord, acc = _target(hass, call)
        rest, pid = acc["Unit"]["RestURL"], acc["Pupil"]["Id"]
        od: date = call.data["date_from"]
        do: date = call.data.get("date_to") or od
        if do < od:
            raise ServiceValidationError("'date_to' jest wcześniejsze niż 'date_from'")
        try:
            surowe = await coord.api.lessons(rest, pid, od, do)
        except (ApiError, TransportError) as err:
            raise HomeAssistantError(str(err)) from err
        wpisy = m.parse_all(m.parse_attendance, surowe)
        return {
            "od": od.isoformat(),
            "do": do.isoformat(),
            "surowych_rekordow": len(surowe or []),
            "rozpoznanych": len(wpisy),
            # same nazwy pól, bez wartości — pozwalają dopasować parser do kształtu,
            # jaki wystawia konkretna szkoła, nie wynosząc treści dziennika
            "pola_rekordu": sorted({k for r in (surowe or []) if isinstance(r, dict) for k in r}),
            "rodzaje": sorted({a.kind for a in wpisy if a.kind}),
            "bez_lesson_class_id": sum(1 for a in wpisy if a.lesson_class_id is None),
            # Stany wniosków o usprawiedliwienie, jakimi posługuje się ta szkoła —
            # sama etykieta statusu, bez powodu wpisanego przez rodzica.
            "statusy": sorted({m.justification_label(r) for r in (surowe or []) if isinstance(r, dict)}),
            "wpisy": [
                {
                    "data": a.day.isoformat(),
                    "lekcja": a.position,
                    "przedmiot": a.subject,
                    "rodzaj": a.kind,
                    "obecny": a.present,
                    "nieobecny": a.absent,
                    "usprawiedliwiona": a.justified,
                    "spoznienie": a.late,
                    "wniosek_w_toku": a.justification_pending,
                    "stan_wniosku": a.justification_status,
                    "do_usprawiedliwienia": a.to_justify,
                }
                for a in sorted(wpisy, key=lambda x: (x.day, x.position or 0))
            ],
        }

    async def schedule(call: ServiceCall) -> ServiceResponse:
        """Plan jednego dnia: numer lekcji, godziny, przedmiot, nauczyciel.

        Potrzebny tam, gdzie trzeba wskazać konkretną lekcję i jej nauczyciela —
        na przykład przy zwolnieniu z części dnia, które trafia do nauczyciela
        ostatniej lekcji, na jakiej uczeń zostaje.
        """
        coord, acc = _target(hass, call)
        rest, pid = acc["Unit"]["RestURL"], acc["Pupil"]["Id"]
        dzien: date = call.data["date"]
        try:
            surowe = await coord.api.schedule(rest, pid, dzien, dzien)
        except (ApiError, TransportError) as err:
            raise HomeAssistantError(str(err)) from err
        lekcje = [l for l in m.parse_all(m.parse_lesson, surowe) if l.day == dzien]
        # ta sama odpowiedź trafia do encji — usługa i sensory nie mogą mówić co innego
        await coord.async_merge_day(acc["Pupil"]["LoginId"], dzien, lekcje)
        return {
            "data": dzien.isoformat(),
            "lekcji": len(lekcje),
            "lekcje": [
                {
                    "lekcja": l.position,
                    "od": l.start.strftime("%H:%M") if l.start else None,
                    "do": l.end.strftime("%H:%M") if l.end else None,
                    "przedmiot": l.subject,
                    "nauczyciel": l.teacher,
                    "sala": l.room,
                    "odwolana": l.cancelled,
                    "zmiana": l.changed,
                }
                for l in sorted(lekcje, key=lambda x: (x.position or 0, x.start or x.day))
            ],
        }

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
    hass.services.async_register(DOMAIN, "read_messages", read_messages, SCHEMA_READ_MESSAGES,
                                 supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "attendance", attendance, SCHEMA_ATTENDANCE,
                                 supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "schedule", schedule, SCHEMA_SCHEDULE,
                                 supports_response=SupportsResponse.ONLY)
    hass.services.async_register(DOMAIN, "refresh", refresh, SCHEMA_REFRESH)
