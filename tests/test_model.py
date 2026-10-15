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


# --- frekwencja ---------------------------------------------------------------


def test_parse_attendance_czyta_flagi():
    wpisy = m.parse_all(m.parse_attendance, dane.LESSONS)
    po_id = {a.key.split("-")[0]: a for a in wpisy}
    assert po_id["P71"].absent and not po_id["P71"].justified and po_id["P71"].to_justify
    assert po_id["P73"].present and not po_id["P73"].to_justify
    assert po_id["P74"].absent and po_id["P74"].justified and not po_id["P74"].to_justify
    assert po_id["P75"].late and not po_id["P75"].excused_late and po_id["P75"].to_justify


def test_parse_attendance_wnioskuje_z_nazwy_bez_flag():
    """Szkoła bez kompletu flag — klasyfikacja musi wyjść ze słownikowej nazwy."""
    wpisy = {a.key.split("-")[0]: a for a in m.parse_all(m.parse_attendance, dane.LESSONS)}
    nn = wpisy["P76"]
    assert nn.absent and not nn.justified and nn.to_justify


def test_parse_attendance_brak_wpisu_to_obecnosc():
    wpisy = {a.key.split("-")[0]: a for a in m.parse_all(m.parse_attendance, dane.LESSONS)}
    assert wpisy["P77"].present and not wpisy["P77"].to_justify


def test_bez_lesson_class_id_nie_da_sie_usprawiedliwic():
    att = m.parse_attendance({"Id": 9, "DateAt": dane.iso(dane.DZIS), "TimeSlot": {"Position": 1},
                              "Subject": {"Name": "X"},
                              "PresenceType": {"Name": "Nieobecność", "Absence": True}})
    assert att.absent and att.lesson_class_id is None and not att.to_justify


def test_widoki_frekwencji():
    p = m.PupilData(pupil_id=1, login_id=2, name="x",
                    attendance=m.parse_all(m.parse_attendance, dane.LESSONS))
    czeka = p.to_justify()
    assert [a.key.split("-")[0] for a in czeka] == ["P76", "P75", "P71", "P72"]  # od najstarszego
    # 6 wpisów z typem (P77 bez typu nie liczy się), nieobecne P71/P72/P74/P76;
    # spóźnienie (P75) to obecność
    assert p.attendance_ratio() == 33.3
    assert m.PupilData(pupil_id=1, login_id=2, name="x").attendance_ratio() is None


def test_record_date_czyta_rozne_nazwy_pol():
    """Hebe nazywa pole z datą różnie; parser ma brać datę lekcji, nie techniczną."""
    assert m.record_date({"DateAt": "2026-10-05"}) == date(2026, 10, 5)
    assert m.record_date({"Day": {"Date": "2026-10-06", "DateDisplay": "06.10.2026"}}) == date(2026, 10, 6)
    assert m.record_date({"LessonDate": {"Date": "2026-10-07"}}) == date(2026, 10, 7)
    # nieznana nazwa, ale wygląda na datę dnia
    assert m.record_date({"DayDateUtc": "2026-10-08"}) == date(2026, 10, 8)
    # daty techniczne odrzucamy
    assert m.record_date({"DateModify": "2026-01-01", "DateCreated": "2026-01-02"}) is None
    assert m.record_date({"Id": 1}) is None


def test_parse_attendance_bierze_date_z_nietypowego_pola():
    a = m.parse_attendance({"Id": 7, "Day": {"Date": "2026-10-05"}, "LessonClassId": 12,
                            "TimeSlot": {"Position": 3}, "Subject": {"Name": "Matematyka"}})
    assert a is not None
    assert a.day == date(2026, 10, 5)
    assert a.present is True
    assert a.to_justify is False


def _obecnosc(nazwa: str, **flagi):
    return m.parse_attendance({
        "Id": 1, "DayAt": {"Date": "2026-09-29"}, "LessonClassId": 5,
        "TimeSlot": {"Position": 2}, "Subject": {"Name": "Matematyka"},
        "PresenceType": {"Name": nazwa, **flagi},
    })


@pytest.mark.parametrize(
    ("nazwa", "do_usprawiedliwienia"),
    [
        ("nieob. uspraw.", False),      # skrót, jakiego używa szkoła Emilki
        ("nieobecność", True),
        ("nieob. nieuspraw.", True),
        ("spóźn. uspraw.", False),
        ("spóźnienie", True),
        ("obecność", False),
    ],
)
def test_typ_obecnosci_rozpoznany_ze_skroconej_nazwy(nazwa, do_usprawiedliwienia):
    """Bez flag w PresenceType decyduje nazwa typu, a szkoły ją skracają."""
    assert _obecnosc(nazwa).to_justify is do_usprawiedliwienia


def test_flagi_biora_gore_nad_nazwa():
    """Gdy szkoła wystawia flagi, nazwa typu jest tylko opisem."""
    a = _obecnosc("nieobecność", Absence=True, AbsenceJustified=True)
    assert a.absent is True and a.justified is True and a.to_justify is False
