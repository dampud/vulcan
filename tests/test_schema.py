"""Inspektor struktury: ma pokazać kształt pól i nie wypuścić treści."""

from __future__ import annotations

from vulcan_client import schema

from . import dane


def test_maska_zostawia_ksztalt_a_nie_tresc():
    assert schema.mask("2026-10-12 08:00:00") == "NNNN-NN-NN NN:NN:NN"
    assert schema.mask("Kowalski") == "Aaaaaaaa"
    assert schema.mask("5a") == "Na"


def test_render_pokazuje_format_daty_i_zagniezdzenia():
    out = schema.render("schedule", dane.SCHEDULE)
    assert "rekordów 5" in out
    assert "[].DateAt" in out and "NNNN-NN-NN" in out
    assert "[].TimeSlot.Start" in out and "NN:NN:NN" in out
    assert "[].Substitution.ClassAbsence" in out
    assert "[].Substitution.Subject.Name" in out


def test_render_nie_pokazuje_wartosci_tekstowych():
    out = schema.render("notes", dane.NOTES)
    for tajne in ("Pomoc koleżeńska", "Spóźnienie na pierwszą lekcję", "Jan Nowakowy", "Nowakowy"):
        assert tajne not in out
    assert "[].Content" in out


def test_dlugi_tekst_bez_maski_tylko_dlugosc():
    dlugi = "x" * (schema.MASK_LIMIT + 10)
    out = schema.render("x", [{"Content": dlugi}])
    assert "tekst" in out and dlugi not in out


def test_puste_i_null_sa_policzone():
    out = schema.render("x", [{"A": None}, {"A": 1}, {}])
    assert "null:1" in out and "1/3" in out or "2/3" in out


def test_values_at_dziala_tylko_na_wskazanej_sciezce():
    liczby = schema.values_at(dane.LESSONS, "[].PresenceType.Name")
    assert liczby["'Nieobecność'"] == 2 and liczby["'Obecność'"] == 1
    assert schema.values_at(dane.LESSONS, "[].Nieistnieje") == {}


def test_values_at_wchodzi_w_listy_zagniezdzone():
    dane_ = [{"Zalaczniki": [{"Typ": "pdf"}, {"Typ": "pdf"}]}, {"Zalaczniki": [{"Typ": "jpg"}]}]
    assert schema.values_at(dane_, "[].Zalaczniki[].Typ") == {"'pdf'": 2, "'jpg'": 1}


def test_summarize_radzi_sobie_z_pojedynczym_obiektem():
    total, pola = schema.summarize(dane.LUCKY)
    assert total == 1
    assert [p.path for p in pola] == ["[].Day", "[].Number"]
