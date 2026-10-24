"""Koordynator: wykrywanie nowości, zdarzenia, cisza nocna, przyrost wiadomości."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.vulcan_dom.coordinator import MESSAGES_HISTORY
from custom_components.vulcan_dom.const import (
    CONF_QUIET_END,
    CONF_QUIET_START,
    EVENT,
    EVENT_TEXT_LIMIT,
)

from . import dane


@pytest.fixture
def zdarzenia(hass: HomeAssistant) -> list:
    zebrane: list = []
    hass.bus.async_listen(EVENT, lambda e: zebrane.append(e.data))
    return zebrane


async def odswiez(hass, entry):
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_pierwsze_pobranie_nie_wysyla_zdarzen(hass, entry, setup_entry, zdarzenia):
    assert entry.state is ConfigEntryState.LOADED
    assert zdarzenia == []


async def test_nowa_ocena_daje_zdarzenie(hass, entry, setup_entry, zdarzenia):
    setup_entry.data["mobile/grade/byPupil"].append({
        "Id": 39, "Content": "6", "CreatedAt": f"{dane.DZIS.isoformat()} 09:00:00",
        "Column": {"Name": "Aktywność", "Weight": 1.0, "Subject": {"Name": "Fizyka"}},
        "Creator": {"DisplayName": "Karol Fizyk"},
    })
    await odswiez(hass, entry)
    nowe = [z for z in zdarzenia if z["type"] == "new_grade"]
    assert len(nowe) == 1
    assert nowe[0]["grade"] == "6" and nowe[0]["subject"] == "Fizyka"
    assert nowe[0]["pupil"] == "Ala Testowa" and nowe[0]["login_id"] == dane.LOGIN_ID


async def test_to_samo_pobranie_drugi_raz_nie_powtarza_zdarzen(hass, entry, setup_entry, zdarzenia):
    await odswiez(hass, entry)
    await odswiez(hass, entry)
    assert zdarzenia == []


async def test_nowa_wiadomosc_i_uwaga(hass, entry, setup_entry, zdarzenia):
    setup_entry.data["mobile/messages/received/byBox"].append(
        dane.message(64, "Nowa sprawa", read=False, days_ago=0)
    )
    setup_entry.data["mobile/note/byPupil"].append({
        "Id": 43, "ValidAt": dane.DZIS.isoformat(), "Positive": False,
        "Category": {"Name": "Zachowanie"}, "Content": "x" * (EVENT_TEXT_LIMIT + 50),
        "Creator": {"DisplayName": "Jan Nowakowy"},
    })
    await odswiez(hass, entry)
    typy = {z["type"] for z in zdarzenia}
    assert typy == {"new_message", "new_note"}
    uwaga = next(z for z in zdarzenia if z["type"] == "new_note")
    assert len(uwaga["content"]) == EVENT_TEXT_LIMIT  # treść przycięta
    assert uwaga["content"].endswith("…")


async def test_zmiana_w_planie_daje_zdarzenie(hass, entry, setup_entry, zdarzenia):
    plan = setup_entry.data["mobile/schedule/withchanges/byPupil"]
    plan[3] = {**plan[3], "Substitution": {
        "Id": 53, "ChangeDateAt": dane.JUTRO.isoformat(),
        "TimeSlot": {"Position": 1, "Start": "09:00:00", "End": "09:45:00"},
        "Subject": None, "TeacherPrimary": None, "ClassAbsence": True, "Reason": "odwołane",
    }}
    await odswiez(hass, entry)
    zmiany = [z for z in zdarzenia if z["type"] == "schedule_change"]
    assert len(zmiany) == 1
    assert zmiany[0]["cancelled"] is True and zmiany[0]["date"] == dane.JUTRO.isoformat()


PLAN = "mobile/schedule/withchanges/byPupil"


async def test_cisza_nocna_wstrzymuje_odpytywanie(hass, entry, setup_entry, frozen_time):
    hass.config_entries.async_update_entry(entry, options={CONF_QUIET_START: 6, CONF_QUIET_END: 8})
    await hass.async_block_till_done()
    przed = len(setup_entry.calls)
    # w ciszy, ale niecałą godzinę po ostatnim pobraniu (06:30) — ani jednego żądania
    frozen_time.move_to(f"{dane.DZIS.isoformat()} 07:00:00+02:00")
    await odswiez(hass, entry)
    assert len(setup_entry.calls) == przed


async def test_cisza_nocna_pobiera_tylko_plan_co_godzine(hass, entry, setup_entry, frozen_time, zdarzenia):
    hass.config_entries.async_update_entry(entry, options={CONF_QUIET_START: 22, CONF_QUIET_END: 6})
    await hass.async_block_till_done()
    przed = len(setup_entry.calls)
    plan = setup_entry.data[PLAN]
    plan[3] = {**plan[3], "Substitution": {
        "Id": 54, "ChangeDateAt": dane.JUTRO.isoformat(),
        "TimeSlot": {"Position": 1, "Start": "09:00:00", "End": "09:45:00"},
        "Subject": None, "TeacherPrimary": None, "ClassAbsence": True, "Reason": "odwołane wieczorem",
    }}
    frozen_time.move_to(f"{dane.DZIS.isoformat()} 23:30:00+02:00")
    await odswiez(hass, entry)
    nowe = setup_entry.calls[przed:]
    assert nowe and {c["path"] for c in nowe} == {PLAN}  # sam plan, bez ocen, skrzynki itd.
    zmiany = [z for z in zdarzenia if z["type"] == "schedule_change"]
    assert len(zmiany) == 1 and zmiany[0]["cancelled"] is True
    assert any(l.cancelled for l in entry.runtime_data.data[dane.LOGIN_ID].lessons)

    # kolejne odświeżenie w tej samej godzinie — cisza
    po_planie = len(setup_entry.calls)
    frozen_time.move_to(f"{dane.DZIS.isoformat()} 23:59:00+02:00")
    await odswiez(hass, entry)
    assert len(setup_entry.calls) == po_planie
    # po godzinie znowu sam plan
    frozen_time.move_to(f"{dane.JUTRO.isoformat()} 00:31:00+02:00")
    await odswiez(hass, entry)
    assert {c["path"] for c in setup_entry.calls[po_planie:]} == {PLAN}


async def test_blad_planu_w_ciszy_nie_psuje_encji(hass, entry, setup_entry, frozen_time):
    hass.config_entries.async_update_entry(entry, options={CONF_QUIET_START: 22, CONF_QUIET_END: 6})
    await hass.async_block_till_done()
    setup_entry.fail[PLAN] = (502, 0)
    frozen_time.move_to(f"{dane.DZIS.isoformat()} 23:30:00+02:00")
    await odswiez(hass, entry)
    assert entry.runtime_data.last_update_success


async def test_usluga_refresh_lamie_cisze_nocna(hass, entry, setup_entry, frozen_time):
    hass.config_entries.async_update_entry(entry, options={CONF_QUIET_START: 22, CONF_QUIET_END: 6})
    await hass.async_block_till_done()
    przed = len(setup_entry.calls)
    frozen_time.move_to(f"{dane.DZIS.isoformat()} 23:30:00+02:00")
    await hass.services.async_call("vulcan_dom", "refresh", {}, blocking=True)
    await hass.async_block_till_done()
    assert len(setup_entry.calls) > przed


async def test_drugie_pobranie_wiadomosci_jest_przyrostowe(hass, entry, setup_entry):
    sciezka = "mobile/messages/received/byBox"
    pierwsze = setup_entry.path_calls(sciezka)
    # pełne pobranie sięga okna historii, nie po całą skrzynkę od epoki
    assert pierwsze[0]["params"]["lastSyncDate"] != "1970-01-01 01:00:00"
    assert str(pierwsze[0]["params"]["lastSyncDate"])[:10] == (
        dane.DZIS - MESSAGES_HISTORY).isoformat()

    setup_entry.data[sciezka].append(dane.message(65, "Świeża", read=False, days_ago=0))
    await odswiez(hass, entry)
    drugie = setup_entry.path_calls(sciezka)[len(pierwsze):]
    assert drugie[0]["params"]["lastSyncDate"] != "1970-01-01 01:00:00"

    uczen = entry.runtime_data.data[dane.PUPIL_ID]
    assert {m.key for m in uczen.messages} == {"msg-61", "msg-62", "msg-63", "msg-65"}
    assert uczen.unread_messages == 2  # stare zostały scalone, nie zgubione


async def test_pelne_pobranie_wiadomosci_po_dobie(hass, entry, setup_entry, frozen_time):
    sciezka = "mobile/messages/received/byBox"
    frozen_time.move_to(f"{(dane.DZIS + timedelta(days=1)).isoformat()} 10:00:00+02:00")
    await odswiez(hass, entry)
    # po dobie znowu pełne pobranie, ale liczone od nowego "dziś" minus okno historii
    assert str(setup_entry.path_calls(sciezka)[-1]["params"]["lastSyncDate"])[:10] == (
        dane.DZIS + timedelta(days=1) - MESSAGES_HISTORY).isoformat()


async def test_odmowa_certyfikatu_prowadzi_do_ponownej_rejestracji(hass, entry, setup_entry):
    setup_entry.fail["mobile/register/hebe"] = (200, 154)  # nie znaleziono certyfikatu
    await odswiez(hass, entry)
    assert any(f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress())


async def test_blad_sieci_nie_wywala_wpisu(hass, entry, setup_entry):
    """Plan lekcji jest twardy: bez niego dane ucznia nie mają sensu, więc błąd tu
    musi zgłosić nieudane odświeżenie. Pozostałe kategorie są izolowane osobno."""
    setup_entry.fail["mobile/schedule/withchanges/byPupil"] = (502, 0)
    await odswiez(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.last_update_success is False
    setup_entry.fail.clear()
    await odswiez(hass, entry)
    assert entry.runtime_data.last_update_success is True


async def test_brak_numerka_nie_psuje_pobierania(hass, entry, setup_entry):
    setup_entry.fail["mobile/school/lucky"] = (200, 200)  # nie znaleziono obiektu
    await odswiez(hass, entry)
    assert entry.runtime_data.last_update_success is True
    assert entry.runtime_data.data[dane.PUPIL_ID].lucky_number is None


async def test_konto_bez_constituent_unit_nie_wywala(hass, entry, setup_entry):
    konto = {k: v for k, v in dane.ACCOUNT.items() if k != "ConstituentUnit"}
    setup_entry.data["mobile/register/hebe"] = [konto]
    await odswiez(hass, entry)
    assert entry.runtime_data.last_update_success is True
    assert entry.runtime_data.data[dane.PUPIL_ID].lucky_number is None


async def test_wyladowanie_wpisu(hass, entry, setup_entry):
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get("sensor.ala_testowa_ostatnia_ocena").state == "unavailable"


async def test_awaria_skrzynki_nie_zabiera_pozostalych_danych(hass, entry, setup_entry):
    """Skrzynka jest największa i najwolniejsza — jej błąd nie może wywalić całej integracji."""
    setup_entry.fail["mobile/messages/received/byBox"] = (502, 0)
    await odswiez(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.last_update_success is True
    uczen = entry.runtime_data.data[dane.PUPIL_ID]
    assert uczen.lessons and uczen.grades  # plan i oceny żyją mimo padniętej skrzynki
    assert hass.states.get("sensor.ala_testowa_pierwsza_lekcja_dzis").state not in (
        "unavailable", "unknown")


async def test_pierwsze_pobranie_pomija_skrzynke(hass, entry, setup_entry):
    """Setup wpisu jest blokujący — skrzynka nie może go przedłużać.

    Po setupie flaga jest już zdjęta (robi to async_setup_entry), więc sprawdzamy
    samo zachowanie bramki: przy włączonej fladze skrzynka nie jest odpytywana.
    """
    coord = entry.runtime_data
    assert coord._skip_messages is False  # setup zdjął flagę i dociągnął w tle

    sciezka = "mobile/messages/received/byBox"
    przed = len(setup_entry.path_calls(sciezka))
    coord._skip_messages = True
    await odswiez(hass, entry)
    assert len(setup_entry.path_calls(sciezka)) == przed  # zero nowych wywołań

    # a dane pozostałych kategorii dalej są pobierane
    uczen = coord.data[dane.PUPIL_ID]
    assert uczen.lessons and uczen.grades

    coord.enable_messages()
    await odswiez(hass, entry)
    assert len(setup_entry.path_calls(sciezka)) > przed


async def test_bledna_kategoria_nie_wywraca_odswiezenia(hass, entry, setup_entry):
    """Serwer potrafi oddać niepoprawną odpowiedź dla jednego zasobu."""
    setup_entry.fail["mobile/grade/byPupil"] = (502, 0)
    await odswiez(hass, entry)
    assert entry.runtime_data.last_update_success is True
    uczen = entry.runtime_data.data[dane.PUPIL_ID]
    assert uczen.lessons and uczen.attendance   # plan i frekwencja nietknięte
    assert uczen.grades == []                   # same oceny puste
    assert hass.states.get("sensor.ala_testowa_ostatnia_synchronizacja").attributes["blad"] is None
