"""Normalizacja odpowiedzi API — bez Home Assistanta."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from custom_components.vulcan_dom import model as m

from . import dane


@pytest.mark.parametrize(
    "raw,oczekiwane",
    [
        ("2026-10-12", date(2026, 10, 12)),
        ("2026-10-12 08:00:00", date(2026, 10, 12)),
        ("2026-10-12T08:00:00", date(2026, 10, 12)),
        ({"Date": "2026-10-12", "Time": "08:00:00"}, date(2026, 10, 12)),
        (datetime(2026, 10, 12, 8), date(2026, 10, 12)),
        (None, None),
        ("bzdura", None),
    ],
)
def test_to_date_znosi_rozne_formaty(raw, oczekiwane):
    assert m.to_date(raw) == oczekiwane


@pytest.mark.parametrize(
    "raw,oczekiwane",
    [("08:00:00", time(8)), ("08:00", time(8)), ({"Time": "15:30:00"}, time(15, 30)), (None, None), ("x", None)],
)
def test_to_time(raw, oczekiwane):
    assert m.to_time(raw) == oczekiwane


def test_to_datetime_dokleja_strefe_warszawska():
    dt = m.to_datetime("2026-10-12 08:00:00")
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 2 * 3600  # CEST
    assert m.to_datetime("2026-10-12T08:00:00+00:00").utcoffset().total_seconds() == 0


def test_parse_lesson_zwykla():
    lesson = m.parse_lesson(dane.SCHEDULE[0])
    assert lesson.subject == "Matematyka"
    assert lesson.teacher == "Jan Nowakowy"
    assert lesson.room == "12"
    assert lesson.position == 1
    assert lesson.start.hour == 8 and lesson.end.minute == 45
    assert not lesson.changed and not lesson.cancelled


def test_parse_lesson_zastepstwo_bierze_dane_z_podmiany():
    lesson = m.parse_lesson(dane.SCHEDULE[1])
    assert lesson.changed and not lesson.cancelled
    assert lesson.subject == "Chemia"  # nie Biologia z planu pierwotnego
    assert lesson.teacher == "Piotr Zastępczy"
    assert lesson.room == "21"
    assert lesson.change_note == "zastępstwo"


def test_parse_lesson_odwolana_przez_nieobecnosc_klasy():
    lesson = m.parse_lesson(dane.SCHEDULE[2])
    assert lesson.cancelled and lesson.changed
    assert "wycieczka" in lesson.change_note


def test_parse_lesson_bez_godzin_odpada():
    assert m.parse_lesson({"Id": 9, "DateAt": "2026-10-12", "TimeSlot": {}}) is None
    assert m.parse_lesson({"Id": 9, "TimeSlot": {"Start": "08:00:00", "End": "08:45:00"}}) is None


def test_parse_all_pomija_smieci_i_niekompletne():
    assert m.parse_all(m.parse_lesson, None) == []
    assert m.parse_all(m.parse_lesson, ["nie-dict", {"Id": 1}]) == []
    assert len(m.parse_all(m.parse_lesson, dane.SCHEDULE)) == len(dane.SCHEDULE)


def test_parse_exam_homework_grade_note_message():
    exam = m.parse_exam(dane.EXAMS[0])
    assert exam.kind == "Sprawdzian" and exam.subject == "Matematyka"
    hw = m.parse_homework(dane.HOMEWORK[0])
    assert hw.subject == "Polski" and hw.day == dane.DZIS + timedelta(days=2)
    grade = m.parse_grade(dane.GRADES[1])
    assert grade.value == "5" and grade.subject == "Biologia" and grade.weight == 1.0
    note = m.parse_note(dane.NOTES[0])
    assert note.positive and note.category == "Pomoc koleżeńska"
    msg = m.parse_message(dane.MESSAGES[2])
    assert msg.key == "msg-63" and msg.read is False and msg.subject == "Prośba o kontakt"


def pupil() -> m.PupilData:
    return m.PupilData(
        pupil_id=dane.PUPIL_ID, login_id=dane.LOGIN_ID, name="Ala Testowa",
        lessons=m.parse_all(m.parse_lesson, dane.SCHEDULE),
        exams=m.parse_all(m.parse_exam, dane.EXAMS),
        homework=m.parse_all(m.parse_homework, dane.HOMEWORK),
        grades=m.parse_all(m.parse_grade, dane.GRADES),
        notes=m.parse_all(m.parse_note, dane.NOTES),
        messages=m.parse_all(m.parse_message, dane.MESSAGES),
    )


def test_widoki_ucznia():
    p = pupil()
    dzis = p.lessons_on(dane.DZIS)
    assert [l.position for l in dzis] == [1, 2]  # odwołana wypada
    assert p.first_lesson(dane.DZIS).subject == "Matematyka"
    assert p.next_school_day(dane.DZIS) == dane.JUTRO
    assert p.unread_messages == 1
    assert p.latest_grade().value == "5"
    assert [e.day for e in p.upcoming_exams(dane.DZIS)] == sorted(e.day for e in p.exams)
    zmiany = p.changes_between(dane.DZIS, dane.POJUTRZE)
    assert [l.position for l in zmiany] == [2, 3]


def test_first_lesson_pomija_dzien_bez_lekcji():
    p = pupil()
    assert p.first_lesson(dane.DZIS + timedelta(days=5)) is None


def test_lesson_change_key_lapie_modyfikacje_zastepstwa():
    a = m.parse_lesson(dane.SCHEDULE[1])
    zmienione = {**dane.SCHEDULE[1], "Substitution": {**dane.SCHEDULE[1]["Substitution"],
                                                      "Room": {"Code": "22"}}}
    b = m.parse_lesson(zmienione)
    assert m.lesson_change_key(a) != m.lesson_change_key(b)


def test_new_items_i_window():
    p = pupil()
    znane = {g.key for g in p.grades[:1]}
    assert [g.key for g in m.new_items(znane, p.grades)] == [g.key for g in p.grades[1:]]
    od, do = m.window(dane.DZIS, 1, 14)
    assert (do - od).days == 15


# --- oceny -------------------------------------------------------------------


@pytest.mark.parametrize(
    "content,value,oczekiwane,z_serwera",
    [
        ("5", None, 5.0, False),
        ("5+", None, 5.5, False),
        ("3-", None, 2.75, False),
        ("3-", 2.9, 2.9, True),  # liczba z serwera wygrywa z naszą konwencją
        ("4", 0, 4.0, False),  # zero traktujemy jak brak wartości
        ("np", None, None, False),
        ("bz", None, None, False),
        ("+", None, None, False),
        ("", None, None, False),
        (None, None, None, False),
        ("7", None, None, False),  # poza skalą
    ],
)
def test_grade_to_number(content, value, oczekiwane, z_serwera):
    assert m.grade_to_number(content, value) == (oczekiwane, z_serwera)


def test_weighted_average_wazy_i_pomija_bez_wartosci():
    p = pupil()
    mat = p.grades_by_subject()["Matematyka"]
    # 4 (waga 3) i 5+ = 5,5 (waga 2); "np" bez wartości nie liczy się wcale
    assert m.weighted_average(mat) == 4.6
    assert m.weighted_average([]) is None


def test_grades_by_subject_grupuje_i_sortuje():
    p = pupil()
    po_przedmiocie = p.grades_by_subject()
    assert list(po_przedmiocie) == ["Biologia", "Matematyka"]
    assert [g.value for g in po_przedmiocie["Biologia"]] == ["3-", "5"]  # od najstarszej


def test_average_po_wszystkich_ocenach():
    p = pupil()
    assert p.average() == 4.41


def test_parse_grade_zapisuje_zrodlo_wartosci():
    oceny = m.parse_all(m.parse_grade, dane.GRADES)
    z_serwera = [g for g in oceny if g.numeric_from_api]
    assert [g.value for g in z_serwera] == ["3-"]
    assert [g.value for g in oceny if g.numeric is None] == ["np"]
