"""Usługi: adresaci, wysyłka wiadomości, usprawiedliwienie, limit dobowy.

Zapisy idą przez atrapę sieci — żadne żądanie nie opuszcza testu.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.vulcan_dom.const import CONF_WRITE_LIMIT, DOMAIN

from . import dane

WYSLIJ = "mobile/messages"
USPRAWIEDLIW = "mobile/presence/justification/lesson"


async def wywolaj(hass, usluga: str, dane_: dict, odpowiedz: bool = True):
    return await hass.services.async_call(DOMAIN, usluga, dane_, blocking=True, return_response=odpowiedz)


async def test_uslugi_sa_zarejestrowane(hass, setup_entry):
    for usluga in ("send_message", "justify_absence", "recipients", "refresh"):
        assert hass.services.has_service(DOMAIN, usluga)


async def test_lista_adresatow(hass, setup_entry):
    out = await wywolaj(hass, "recipients", {})
    assert out["recipients"] == ["Ewa Przykładowa", "Jan Nowakowy", "Maria Polonistka"]
    out = await wywolaj(hass, "recipients", {"search": "polon"})
    assert out["recipients"] == ["Maria Polonistka"]


async def test_wyslanie_wiadomosci_sklada_poprawna_koperte(hass, setup_entry):
    out = await wywolaj(hass, "send_message", {
        "recipient": "Nowakowy", "subject": "Zwolnienie", "message": "Ala będzie nieobecna w piątek.",
    })
    assert out == {"sent_to": "Jan Nowakowy"}
    koperty = setup_entry.bodies(WYSLIJ)
    assert len(koperty) == 1
    wyslane = koperty[0]
    assert wyslane["Subject"] == "Zwolnienie"
    assert wyslane["Content"] == "Ala będzie nieobecna w piątek."
    assert wyslane["Sender"] == {"GlobalKey": dane.BOX, "Name": "Rodzic Testowy"}
    assert wyslane["Receiver"] == [{"GlobalKey": "t-1", "Name": "Jan Nowakowy"}]


async def test_niejednoznaczny_adresat_nie_wysyla(hass, setup_entry):
    with pytest.raises(ServiceValidationError):
        await wywolaj(hass, "send_message", {"recipient": "a", "subject": "T", "message": "x"})
    assert setup_entry.path_calls(WYSLIJ) == []


async def test_nieznany_adresat_nie_wysyla(hass, setup_entry):
    with pytest.raises(ServiceValidationError):
        await wywolaj(hass, "send_message", {"recipient": "Nikt Taki", "subject": "T", "message": "x"})
    assert setup_entry.path_calls(WYSLIJ) == []


async def test_blad_serwera_przy_wysylce(hass, setup_entry):
    setup_entry.fail[WYSLIJ] = (200, 214)
    with pytest.raises(HomeAssistantError):
        await wywolaj(hass, "send_message", {"recipient": "Nowakowy", "subject": "T", "message": "x"})


async def test_limit_dobowy_zatrzymuje_petle(hass, entry, setup_entry):
    hass.config_entries.async_update_entry(entry, options={CONF_WRITE_LIMIT: 2})
    await hass.async_block_till_done()
    for i in range(2):
        await wywolaj(hass, "send_message", {"recipient": "Nowakowy", "subject": f"T{i}", "message": "x"})
    with pytest.raises(ServiceValidationError):
        await wywolaj(hass, "send_message", {"recipient": "Nowakowy", "subject": "T3", "message": "x"})
    assert len(setup_entry.path_calls(WYSLIJ)) == 2


async def test_usprawiedliwienie_bierze_tylko_nieusprawiedliwione(hass, setup_entry):
    wczoraj = (dane.DZIS - timedelta(days=1)).isoformat()
    out = await wywolaj(hass, "justify_absence", {"date": wczoraj, "reason": "Choroba"})
    assert out["lessons"] == [1, 2]  # lekcja 3 była obecnością
    koperty = setup_entry.bodies(USPRAWIEDLIW)
    assert [k["LessonClassId"] for k in koperty] == [701, 702]
    assert all(k["Reason"] == "Choroba" for k in koperty)
    assert all(k["PupilId"] == dane.PUPIL_ID and k["LoginId"] == dane.LOGIN_ID for k in koperty)


async def test_usprawiedliwienie_wskazanych_lekcji(hass, setup_entry):
    wczoraj = (dane.DZIS - timedelta(days=1)).isoformat()
    out = await wywolaj(hass, "justify_absence", {"date": wczoraj, "reason": "Wizyta", "lessons": [2]})
    assert out["lessons"] == [2]
    assert [k["LessonClassId"] for k in setup_entry.bodies(USPRAWIEDLIW)] == [702]


async def test_dzien_bez_nieobecnosci_nie_wysyla_nic(hass, setup_entry):
    with pytest.raises(ServiceValidationError):
        await wywolaj(hass, "justify_absence", {"date": dane.DZIS.isoformat(), "reason": "Choroba"})
    assert setup_entry.path_calls(USPRAWIEDLIW) == []


async def test_zbyt_krotki_powod_odrzucony(hass, setup_entry):
    with pytest.raises(Exception):
        await wywolaj(hass, "justify_absence", {"date": dane.DZIS.isoformat(), "reason": "x"})
    assert setup_entry.path_calls(USPRAWIEDLIW) == []


async def test_nieznany_uczen(hass, setup_entry):
    with pytest.raises(ServiceValidationError):
        await wywolaj(hass, "recipients", {"pupil": "Kazimierz"})


async def test_usprawiedliwienie_pomija_juz_usprawiedliwione_i_bierze_spoznienie(hass, setup_entry):
    """Dzień z nieobecnością usprawiedliwioną (lekcja 1) i spóźnieniem (lekcja 2)."""
    dzien = (dane.DZIS - timedelta(days=2)).isoformat()
    out = await wywolaj(hass, "justify_absence", {"date": dzien, "reason": "Autobus"})
    assert out["lessons"] == [2]  # lekcja 1 była już usprawiedliwiona
    assert [k["LessonClassId"] for k in setup_entry.bodies(USPRAWIEDLIW)] == [705]


async def test_usprawiedliwienie_bez_flag_po_samej_nazwie(hass, setup_entry):
    """Szkoła bez kompletu flag — 'Nieobecność nieusprawiedliwiona' ma się dać usprawiedliwić."""
    dzien = (dane.DZIS - timedelta(days=3)).isoformat()
    out = await wywolaj(hass, "justify_absence", {"date": dzien, "reason": "Choroba"})
    assert out["lessons"] == [1]  # lekcja 2 (WF) nie ma wpisu frekwencji
    assert [k["LessonClassId"] for k in setup_entry.bodies(USPRAWIEDLIW)] == [706]

async def test_czytanie_wiadomosci_zwraca_tresc(hass, setup_entry):
    out = await wywolaj(hass, "read_messages", {})
    assert out["count"] >= 1 and len(out["messages"]) == out["count"]  # poniżej limitu 10
    pierwsza = out["messages"][0]
    assert set(pierwsza) == {"key", "thread_key", "sent", "sender", "subject", "read", "content"}
    assert pierwsza["content"]  # treść, nie sam temat
    # najnowsze na górze
    wyslane = [m["sent"] for m in out["messages"] if m["sent"]]
    assert wyslane == sorted(wyslane, reverse=True)


async def test_czytanie_tylko_nieprzeczytanych_i_szukanie(hass, setup_entry):
    out = await wywolaj(hass, "read_messages", {"unread_only": True})
    assert out["count"] >= 1
    assert all(m["read"] is False for m in out["messages"])

    wszystkie = await wywolaj(hass, "read_messages", {})
    nadawca = wszystkie["messages"][0]["sender"]
    znalezione = await wywolaj(hass, "read_messages", {"search": nadawca[:4].lower()})
    assert znalezione["count"] >= 1
    assert all(nadawca[:4].lower() in (m["sender"] or "").lower()
               or nadawca[:4].lower() in (m["subject"] or "").lower()
               for m in znalezione["messages"])


async def test_czytanie_respektuje_limit(hass, setup_entry):
    out = await wywolaj(hass, "read_messages", {"limit": 1})
    assert len(out["messages"]) == 1
    assert out["count"] >= 1  # count to liczba pasujących, nie zwróconych


async def test_odczyt_frekwencji_dla_zakresu(hass, setup_entry):
    """Odczyt na żądanie — rozstrzyga, czy pusto jest po stronie serwera, czy parsera."""
    wczoraj = (dane.DZIS - timedelta(days=1)).isoformat()
    out = await wywolaj(hass, "attendance", {"date_from": wczoraj})
    assert out["od"] == wczoraj and out["do"] == wczoraj
    assert out["surowych_rekordow"] >= out["rozpoznanych"] >= 1
    assert "Nieobecność" in out["rodzaje"]
    wpis = out["wpisy"][0]
    assert set(wpis) == {"data", "lekcja", "przedmiot", "rodzaj", "obecny", "nieobecny",
                         "usprawiedliwiona", "spoznienie", "do_usprawiedliwienia",
                         "wniosek_w_toku", "stan_wniosku"}
    # bez stanu wniosku nie da się odróżnić lekcji z wysłanym wnioskiem od nietkniętej
    assert isinstance(wpis["wniosek_w_toku"], bool)
    assert "statusy" in out and "pola_rekordu" in out


async def test_odczyt_frekwencji_zakres_wielodniowy_i_sortowanie(hass, setup_entry):
    out = await wywolaj(hass, "attendance", {
        "date_from": (dane.DZIS - timedelta(days=3)).isoformat(),
        "date_to": dane.DZIS.isoformat(),
    })
    klucze = [(w["data"], w["lekcja"]) for w in out["wpisy"]]
    assert klucze == sorted(klucze)


async def test_odczyt_frekwencji_odwrocony_zakres_odrzucony(hass, setup_entry):
    with pytest.raises(ServiceValidationError):
        await wywolaj(hass, "attendance", {
            "date_from": dane.DZIS.isoformat(),
            "date_to": (dane.DZIS - timedelta(days=5)).isoformat(),
        })
