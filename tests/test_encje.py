"""Sensory, kalendarze i urządzenie ucznia."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.vulcan_dom.const import DOMAIN

from . import dane

PIERWSZA_DZIS = "sensor.ala_testowa_pierwsza_lekcja_dzis"
PIERWSZA_JUTRO = "sensor.ala_testowa_pierwsza_lekcja_jutro"
NASTEPNY_DZIEN = "sensor.ala_testowa_pierwsza_lekcja_nastepnego_dnia_nauki"
SPRAWDZIAN = "sensor.ala_testowa_najblizszy_sprawdzian"
SPRAWDZIANY_7 = "sensor.ala_testowa_sprawdziany_w_7_dni"
ZMIANY = "sensor.ala_testowa_zmiany_w_planie_7_dni"
OCENA = "sensor.ala_testowa_ostatnia_ocena"
OCENY = "sensor.ala_testowa_oceny"
WIADOMOSCI = "sensor.ala_testowa_nieprzeczytane_wiadomosci"
UWAGI = "sensor.ala_testowa_uwagi"
NUMEREK = "sensor.ala_testowa_szczesliwy_numerek"
SYNC = "sensor.ala_testowa_ostatnia_synchronizacja"
KALENDARZ_LEKCJI = "calendar.ala_testowa_plan_lekcji"
KALENDARZ_ZADAN = "calendar.ala_testowa_sprawdziany_i_zadania"


def godzina(stan: str) -> datetime:
    return dt_util.parse_datetime(stan).astimezone(dt_util.DEFAULT_TIME_ZONE)


async def test_pierwsza_lekcja_dzis(hass, setup_entry):
    stan = hass.states.get(PIERWSZA_DZIS)
    assert godzina(stan.state) == datetime(2026, 10, 12, 8, 0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
    assert stan.attributes["przedmiot"] == "Matematyka"
    assert stan.attributes["sala"] == "12"
    assert stan.attributes["lekcja"] == 1
    assert stan.attributes["zmiana"] is False


async def test_pierwsza_lekcja_jutro_i_nastepnego_dnia(hass, setup_entry):
    assert godzina(hass.states.get(PIERWSZA_JUTRO).state).hour == 9
    assert godzina(hass.states.get(NASTEPNY_DZIEN).state).date() == dane.JUTRO


async def test_nastepny_dzien_nauki_przeskakuje_weekend(hass, entry, setup_entry):
    """Gdy jutra nie ma w planie, czujnik 'następnego dnia nauki' bierze kolejny z planem."""
    plan = [l for l in setup_entry.data["mobile/schedule/withchanges/byPupil"]
            if l["DateAt"] != dane.JUTRO.isoformat()]
    setup_entry.data["mobile/schedule/withchanges/byPupil"] = plan
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(PIERWSZA_JUTRO).state == "unknown"
    assert godzina(hass.states.get(NASTEPNY_DZIEN).state).date() == dane.POJUTRZE


async def test_sprawdziany(hass, setup_entry):
    stan = hass.states.get(SPRAWDZIAN)
    assert stan.state == (dane.DZIS + timedelta(days=3)).isoformat()
    assert stan.attributes["przedmiot"] == "Matematyka"
    assert len(stan.attributes["wszystkie"]) == 2
    assert hass.states.get(SPRAWDZIANY_7).state == "1"


async def test_zmiany_w_planie_licza_zastepstwo_i_odwolanie(hass, setup_entry):
    stan = hass.states.get(ZMIANY)
    assert stan.state == "2"
    opisy = stan.attributes["zmiany"]
    assert any("ODWOŁANA" in o for o in opisy)
    assert any("Chemia" in o for o in opisy)


async def test_oceny_wiadomosci_uwagi_numerek(hass, setup_entry):
    ocena = hass.states.get(OCENA)
    assert ocena.state == "5" and ocena.attributes["przedmiot"] == "Biologia"
    assert hass.states.get(WIADOMOSCI).state == "1"
    assert len(hass.states.get(WIADOMOSCI).attributes["ostatnie"]) == 1
    uwagi = hass.states.get(UWAGI)
    assert uwagi.state == "2" and uwagi.attributes["pozytywne"] == 1 and uwagi.attributes["negatywne"] == 1
    assert hass.states.get(NUMEREK).state == "13"


async def test_sensor_synchronizacji_zyje_mimo_bledu(hass, entry, setup_entry):
    setup_entry.fail["mobile/register/hebe"] = (502, 0)
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    stan = hass.states.get(SYNC)
    assert stan.state not in ("unavailable", "unknown")
    assert stan.attributes["ok"] is False and stan.attributes["blad"]


async def test_kalendarz_lekcji_pokazuje_zastepstwo_i_odwolanie(hass, setup_entry):
    start = dt_util.start_of_local_day(dane.DZIS)
    wydarzenia = await hass.services.async_call(
        "calendar", "get_events",
        {"entity_id": KALENDARZ_LEKCJI, "start_date_time": start,
         "end_date_time": start + timedelta(days=1)},
        blocking=True, return_response=True,
    )
    lekcje = wydarzenia[KALENDARZ_LEKCJI]["events"]
    assert [e["summary"] for e in lekcje] == [
        "1 Matematyka", "Zmiana: 2 Chemia", "ODWOŁANA: 3 Historia",
    ]
    assert lekcje[1]["location"] == "21"
    assert "Piotr Zastępczy" in lekcje[1]["description"]


async def test_kalendarz_lekcji_pomija_odwolane_w_biezacym_wydarzeniu(hass, setup_entry):
    stan = hass.states.get(KALENDARZ_LEKCJI)
    assert stan.attributes["message"] == "1 Matematyka"


async def test_kalendarz_zadan(hass, setup_entry):
    start = dt_util.start_of_local_day(dane.DZIS)
    wydarzenia = await hass.services.async_call(
        "calendar", "get_events",
        {"entity_id": KALENDARZ_ZADAN, "start_date_time": start,
         "end_date_time": start + timedelta(days=10)},
        blocking=True, return_response=True,
    )
    tematy = [e["summary"] for e in wydarzenia[KALENDARZ_ZADAN]["events"]]
    assert "Sprawdzian: Matematyka" in tematy
    assert "Zadanie: Polski" in tematy


async def test_jedno_urzadzenie_na_ucznia(hass, entry, setup_entry):
    devices = dr.async_get(hass)
    device = devices.async_get_device(identifiers={(DOMAIN, str(dane.LOGIN_ID))})
    assert device is not None and device.name == "Ala Testowa"
    assert device.model == "klasa 5a"
    entities = er.async_get(hass)
    nasze = er.async_entries_for_device(entities, device.id, include_disabled_entities=True)
    assert len(nasze) == 14  # 12 sensorów + 2 kalendarze
    assert all(e.config_entry_id == entry.entry_id for e in nasze)


async def test_sensor_ocen_srednie_i_podzial_na_przedmioty(hass, setup_entry):
    stan = hass.states.get(OCENY)
    assert stan.state == "4.41"
    assert stan.attributes["liczba_ocen"] == 5
    assert stan.attributes["bez_wartosci"] == 1
    assert stan.attributes["wartosc_z_serwera"] == 1

    przedmioty = {p["przedmiot"]: p for p in stan.attributes["przedmioty"]}
    assert set(przedmioty) == {"Biologia", "Matematyka"}
    assert przedmioty["Matematyka"]["srednia"] == 4.6
    assert przedmioty["Biologia"]["srednia"] == 3.95
    assert przedmioty["Matematyka"]["liczba"] == 3

    oceny = przedmioty["Matematyka"]["oceny"]
    assert [o["ocena"] for o in oceny] == ["np", "4", "5+"]
    assert [o["waga"] for o in oceny] == [0.0, 3.0, 2.0]
    assert oceny[0]["wartosc"] is None and oceny[2]["wartosc"] == 5.5
