"""Normalizacja surowych odpowiedzi API do prostych struktur dla HA.

Bez importów Home Assistanta — testowalne samodzielnie. Pola wejściowe wg
modeli iris (PascalCase). Parsowanie dat jest defensywne: API zwraca daty
jako tekst ISO ("2026-10-12", "2026-10-12 08:00:00"), ale stare wersje
zwracały obiekty {"Date": ..., "Time": ...}.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Warsaw")
EPOCH = datetime(1970, 1, 1, tzinfo=TZ)

# Ocena bez wartości z serwera: ile dokłada plus, ile zabiera minus. Szkoła
# konfiguruje to po swojemu, więc liczymy tak tylko wtedy, gdy API nie poda
# gotowej liczby — patrz grade_to_number().
GRADE_PLUS = 0.5
GRADE_MINUS = -0.25
GRADE_RE = re.compile(r"^\s*([1-6])\s*([+-])?\s*$")


# --- daty ------------------------------------------------------------------


def to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("Date") or value.get("date")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def to_time(value: Any) -> time | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("Time") or value.get("time")
    try:
        return time.fromisoformat(str(value)[:8] if len(str(value)) >= 8 else str(value))
    except ValueError:
        return None


def to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, dict):
        d, t = to_date(value), to_time(value)
        return datetime.combine(d, t or time(0), TZ) if d else None
    try:
        dt = datetime.fromisoformat(str(value).replace(" ", "T"))
    except ValueError:
        d = to_date(value)
        return datetime.combine(d, time(0), TZ) if d else None
    return dt if dt.tzinfo else dt.replace(tzinfo=TZ)


def _name(obj: Any, key: str = "Name") -> str | None:
    return obj.get(key) if isinstance(obj, dict) else None


# --- oceny -------------------------------------------------------------------


def grade_to_number(content: Any, value: Any = None) -> tuple[float | None, bool]:
    """Liczbowa wartość oceny i skąd pochodzi.

    Pierwszeństwo ma liczba z serwera (pole `Value`), bo to szkoła ustala, ile
    wart jest plus i minus — zgadywanie dawałoby średnie rozjeżdżające się z tym,
    co widać w dzienniku. Dopiero gdy serwer jej nie poda, czytamy sam tekst
    oceny. Wpisy bez wartości liczbowej ("np", "bz", "+", "-") zwracają None i
    nie wchodzą do średniej.
    """
    if isinstance(value, bool):
        value = None
    if isinstance(value, (int, float)) and value > 0:
        return float(value), True
    match = GRADE_RE.match(str(content or ""))
    if not match:
        return None, False
    base = float(match.group(1))
    sign = match.group(2)
    return base + (GRADE_PLUS if sign == "+" else GRADE_MINUS if sign == "-" else 0.0), False


SKALA_1_6 = "1-6"
SKALA_PROCENT = "procent"


def grade_scale(grades: list["Grade"]) -> str:
    """Skala ocen przedmiotu: procentowa, gdy którakolwiek ocena wykracza poza 1–6.

    Klasy 1–3 dostają zwykle oceny procentowe (0–100), a religia czy etyka bywa w tych
    samych klasach oceniana w skali 1–6. Rozpoznajemy po przedmiocie, nie po pojedynczej
    ocenie — inaczej 5% z kartkówki trafiłoby do skali 1–6.
    """
    return SKALA_PROCENT if any(g.numeric is not None and g.numeric > 6 for g in grades) else SKALA_1_6


def weighted_average(grades: list["Grade"]) -> float | None:
    """Średnia ważona ocen mających wartość liczbową; brak wagi liczymy jako 1."""
    pairs = [(g.numeric, g.weight if g.weight and g.weight > 0 else 1.0) for g in grades if g.numeric is not None]
    total = sum(w for _, w in pairs)
    if not pairs or not total:
        return None
    return round(sum(v * w for v, w in pairs) / total, 2)


def _teacher(obj: Any) -> str | None:
    if not isinstance(obj, dict):
        return None
    return obj.get("DisplayName") or " ".join(filter(None, [obj.get("Name"), obj.get("Surname")])) or None


# --- struktury ---------------------------------------------------------------


@dataclass
class Lesson:
    key: str
    day: date
    start: datetime
    end: datetime
    position: int | None
    subject: str
    teacher: str | None
    room: str | None
    group: str | None
    changed: bool = False
    cancelled: bool = False
    change_note: str | None = None


@dataclass
class Exam:
    key: str
    day: date
    subject: str
    kind: str
    content: str
    teacher: str | None


@dataclass
class Homework:
    key: str
    day: date
    subject: str
    content: str
    teacher: str | None


@dataclass
class Grade:
    key: str
    value: str
    subject: str
    column: str | None
    weight: float | None
    teacher: str | None
    created: datetime | None
    modified: datetime | None
    numeric: float | None = None
    # True = liczbę podał serwer (pole Value), False = policzyliśmy z tekstu oceny.
    # Diagnostyka: pokazuje, czy średnie opierają się na konwencji szkoły, czy naszej.
    numeric_from_api: bool = False


@dataclass
class Attendance:
    """Jedna lekcja z punktu widzenia frekwencji."""

    key: str
    day: date
    position: int | None
    subject: str
    kind: str                      # nazwa typu obecności ze słownika szkoły
    present: bool                  # obecny (albo nic nie odnotowano)
    absent: bool
    justified: bool
    late: bool
    excused_late: bool
    lesson_class_id: int | None    # potrzebne do usprawiedliwienia
    justification_pending: bool = False   # wniosek wysłany, czeka na wychowawcę
    justification_status: str = "brak"    # etykieta stanu wniosku, do podglądu

    @property
    def to_justify(self) -> bool:
        """Nieobecność albo spóźnienie, z którym da się coś zrobić TERAZ.

        Wniosek już wysłany nie jest „do usprawiedliwienia": dopóki wychowawca go
        nie rozpatrzy, typ obecności się nie zmienia, więc bez tego warunku automat
        wysyłałby ten sam wniosek przy każdym odświeżeniu.
        """
        if self.lesson_class_id is None or self.justification_pending:
            return False
        if self.absent and not self.justified:
            return True
        return self.late and not self.excused_late


@dataclass
class Note:
    key: str
    day: date | None
    positive: bool
    category: str | None
    content: str
    teacher: str | None


@dataclass
class Message:
    key: str
    thread_key: str | None
    subject: str
    sender: str | None
    sent: datetime | None
    read: bool
    content: str


@dataclass
class PupilData:
    pupil_id: int
    login_id: int
    name: str
    lessons: list[Lesson] = field(default_factory=list)
    exams: list[Exam] = field(default_factory=list)
    homework: list[Homework] = field(default_factory=list)
    grades: list[Grade] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    attendance: list[Attendance] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    lucky_number: int | None = None

    # --- widoki dla encji ---

    def lessons_on(self, day: date) -> list[Lesson]:
        return sorted((l for l in self.lessons if l.day == day and not l.cancelled), key=lambda l: l.start)

    def first_lesson(self, day: date) -> Lesson | None:
        lessons = self.lessons_on(day)
        return lessons[0] if lessons else None

    def next_school_day(self, after: date) -> date | None:
        days = sorted({l.day for l in self.lessons if l.day > after and not l.cancelled})
        return days[0] if days else None

    def upcoming_exams(self, today: date) -> list[Exam]:
        return sorted((e for e in self.exams if e.day >= today), key=lambda e: e.day)

    def changes_between(self, start: date, end: date) -> list[Lesson]:
        return sorted(
            (l for l in self.lessons if start <= l.day <= end and (l.changed or l.cancelled)),
            key=lambda l: l.start,
        )

    @property
    def unread_messages(self) -> int:
        return sum(1 for m in self.messages if not m.read)

    def latest_grade(self) -> Grade | None:
        dated = [g for g in self.grades if g.created]
        return max(dated, key=lambda g: g.created) if dated else None

    def to_justify(self) -> list[Attendance]:
        """Wpisy frekwencji czekające na usprawiedliwienie, od najstarszego."""
        return sorted((a for a in self.attendance if a.to_justify), key=lambda a: (a.day, a.position or 0))

    def pending_justifications(self) -> list[Attendance]:
        """Lekcje z wnioskiem wysłanym, a nierozpatrzonym — od najstarszej.

        Nie są „do usprawiedliwienia", ale muszą być widoczne: inaczej znikają
        z pola widzenia aż do decyzji wychowawcy i wyglądają jak załatwione.
        """
        return sorted(
            (a for a in self.attendance if a.justification_pending),
            key=lambda a: (a.day, a.position or 0),
        )

    def attendance_on(self, day: date) -> list[Attendance]:
        return sorted((a for a in self.attendance if a.day == day), key=lambda a: a.position or 0)

    def attendance_ratio(self) -> float | None:
        """Odsetek obecności w pobranym oknie; None, gdy nie ma czego liczyć."""
        znane = [a for a in self.attendance if a.kind]
        if not znane:
            return None
        obecne = sum(1 for a in znane if not a.absent)
        return round(100 * obecne / len(znane), 1)

    def grades_by_subject(self) -> dict[str, list[Grade]]:
        """Oceny pogrupowane po przedmiocie: przedmioty alfabetycznie, oceny od najstarszej."""
        out: dict[str, list[Grade]] = {}
        for grade in sorted(self.grades, key=lambda g: (g.created is not None, g.created or EPOCH)):
            out.setdefault(grade.subject, []).append(grade)
        return dict(sorted(out.items()))

    def grades_by_scale(self) -> dict[str, list[Grade]]:
        """Oceny rozdzielone na skale (1–6 i procentową) — skalę wyznacza przedmiot."""
        out: dict[str, list[Grade]] = {}
        for grades in self.grades_by_subject().values():
            out.setdefault(grade_scale(grades), []).extend(grades)
        return out

    def averages(self) -> dict[str, float]:
        """Średnia ważona osobno dla każdej skali, w której są oceny z wartością."""
        out = {skala: weighted_average(grades) for skala, grades in self.grades_by_scale().items()}
        return {skala: avg for skala, avg in out.items() if avg is not None}

    def main_scale(self) -> str | None:
        """Skala z największą liczbą ocen mających wartość liczbową."""
        liczby = {
            skala: sum(1 for g in grades if g.numeric is not None)
            for skala, grades in self.grades_by_scale().items()
        }
        liczby = {skala: n for skala, n in liczby.items() if n}
        return max(liczby, key=lambda s: (liczby[s], s == SKALA_1_6)) if liczby else None

    def average(self) -> float | None:
        """Średnia ważona w dominującej skali — orientacyjna, nie jest to średnia ocen rocznych.

        Procentów i ocen 1–6 nie mieszamy: średnia z 100% i szóstki nic nie znaczy.
        Średnie wszystkich skal są w averages().
        """
        skala = self.main_scale()
        return self.averages().get(skala) if skala else None


# --- parsery -----------------------------------------------------------------


def parse_lesson(raw: dict) -> Lesson | None:
    sub = raw.get("Substitution") or None
    slot = (sub or {}).get("TimeSlot") or raw.get("TimeSlot") or {}
    day = to_date((sub or {}).get("ChangeDateAt")) or to_date(raw.get("DateAt"))
    start_t, end_t = to_time(slot.get("Start")), to_time(slot.get("End"))
    if not day or not start_t or not end_t:
        return None
    subject = _name((sub or {}).get("Subject")) or _name(raw.get("Subject")) or raw.get("Event") or "Zajęcia"
    teacher = _teacher((sub or {}).get("TeacherPrimary")) or _teacher(raw.get("TeacherPrimary"))
    room = _name((sub or {}).get("Room"), "Code") or _name(raw.get("Room"), "Code")
    group = _name(raw.get("Distribution"))
    cancelled = False
    note = None
    if sub:
        # Do weryfikacji na realnych danych: odwołanie = brak przedmiotu i nauczyciela
        # w zastępstwie albo ClassAbsence (nieobecność klasy).
        cancelled = bool(sub.get("ClassAbsence")) or (not sub.get("Subject") and not sub.get("TeacherPrimary"))
        note = "; ".join(
            filter(None, [sub.get("PupilNote"), sub.get("Reason"), sub.get("TeacherAbsenceEffectName"), sub.get("Description")])
        ) or None
    return Lesson(
        key=f"L{raw.get('Id')}-{day.isoformat()}",
        day=day,
        start=datetime.combine(day, start_t, TZ),
        end=datetime.combine(day, end_t, TZ),
        position=slot.get("Position"),
        subject=subject,
        teacher=teacher,
        room=room,
        group=group,
        changed=sub is not None,
        cancelled=cancelled,
        change_note=note,
    )


def parse_exam(raw: dict) -> Exam | None:
    day = to_date(raw.get("DeadlineAt"))
    if not day:
        return None
    return Exam(
        key=f"E{raw.get('Id')}",
        day=day,
        subject=_name(raw.get("Subject")) or "?",
        kind=raw.get("Type") or "sprawdzian",
        content=raw.get("Content") or "",
        teacher=_teacher(raw.get("Creator")),
    )


def parse_homework(raw: dict) -> Homework | None:
    day = to_date(raw.get("DeadlineAt")) or to_date(raw.get("DateAt"))
    if not day:
        return None
    return Homework(
        key=f"H{raw.get('Id')}",
        day=day,
        subject=_name(raw.get("Subject")) or "?",
        content=raw.get("Content") or "",
        teacher=_teacher(raw.get("Creator")),
    )


def parse_grade(raw: dict) -> Grade:
    column = raw.get("Column") or {}
    content = raw.get("Content") or raw.get("ContentRaw") or ""
    numeric, from_api = grade_to_number(content, raw.get("Value"))
    return Grade(
        key=f"G{raw.get('Id')}",
        value=content,
        subject=_name(column.get("Subject")) or "?",
        column=column.get("Name") or column.get("Code"),
        weight=column.get("Weight"),
        teacher=_teacher(raw.get("Creator")),
        created=to_datetime(raw.get("CreatedAt")),
        modified=to_datetime(raw.get("ModifiedAt")),
        numeric=numeric,
        numeric_from_api=from_api,
    )


# Nazwy pola z datą lekcji różnią się między instalacjami Hebe, a rekord niesie też
# daty techniczne (modyfikacja, synchronizacja), których brać nie wolno.
DATE_KEYS = ("DateAt", "Date", "Day", "LessonDate", "DayDate")
DATE_KEYS_ODRZUC = ("modif", "creat", "sync", "deadline", "change")


def record_date(raw: dict) -> date | None:
    """Data rekordu: najpierw znane nazwy pól, potem dowolne pole dat/day poza technicznymi."""
    for key in DATE_KEYS:
        if (day := to_date(raw.get(key))):
            return day
    for key, value in raw.items():
        niska = key.lower()
        if ("date" in niska or "day" in niska) and not any(z in niska for z in DATE_KEYS_ODRZUC):
            if (day := to_date(value)):
                return day
    return None


def justification_label(raw: dict) -> str:
    """Etykieta stanu wniosku o usprawiedliwienie — sam status, bez powodu.

    Kształt `JustificationStatus` zależy od szkoły (bywa słownikiem, tekstem albo
    flagą), a powód wpisany przez rodzica to treść, której nie wynosimy. Zwracamy
    więc wyłącznie nazwę stanu albo 'brak'.
    """
    value = raw.get("JustificationStatus")
    if value is None:
        return "brak"
    if isinstance(value, bool):
        return "tak" if value else "nie"
    if isinstance(value, dict):
        return (_name(value) or value.get("Symbol") or type_or_blank(value)).strip() or "brak"
    return str(value).strip() or "brak"


def justification_pending(raw: dict, justified: bool = False) -> bool:
    """Czy na tę lekcję wisi nierozpatrzony wniosek o usprawiedliwienie.

    `JustificationStatus` ma trzy stany, sprawdzone na żywych danych 18.10.2026:
    `0` — wniosek czeka na wychowawcę; `1` — wniosek zatwierdzony (typ obecności
    zmienia się wtedy na „nieob. uspraw.”, a flaga usprawiedliwienia na prawdę);
    `null` — wniosku przez aplikację nie było (dzień usprawiedliwiony inaczej albo
    wcale). Wcześniej zakładaliśmy, że pole czyści się po decyzji — nieprawda,
    zostaje z wartością 1, więc liczenie „cokolwiek niepustego = w toku” wrzucało
    zatwierdzone do czekających.

    Rozstrzyga więc flaga usprawiedliwienia, nie sama liczba: wniosek jest w toku,
    gdy status istnieje, a nieobecność wciąż nie jest usprawiedliwiona. Działa też,
    gdy szkoła oznacza stany innymi liczbami, a nieznana wartość przy wciąż
    nieusprawiedliwionej nieobecności nadal blokuje powtórną wysyłkę — wolimy nie
    wysłać drugi raz niż zasypać wychowawcę. Surowa wartość jest w
    `justification_status`, więc taki przypadek da się wyłapać.
    """
    value = raw.get("JustificationStatus")
    if value is None or value is False:
        return False
    return not justified


def type_or_blank(value: dict) -> str:
    """Gdy słownik nie ma nazwy, pokazujemy same nazwy jego pól, nie wartości."""
    return "+".join(sorted(value)) if value else "brak"


def _flag(obj: dict, *keys: str) -> bool | None:
    """Pierwsza obecna flaga boolowska spośród podanych kluczy; None gdy żadnej nie ma."""
    for key in keys:
        value = obj.get(key)
        if isinstance(value, bool):
            return value
    return None


def parse_attendance(raw: dict) -> Attendance | None:
    """Frekwencja jednej lekcji.

    Kształt `PresenceType` jest konfigurowany przez szkołę i nie wszystkie instalacje
    wystawiają komplet flag, dlatego czytamy je defensywnie: najpierw flagi
    (`Absence`, `AbsenceJustified`, `Late`, `LateExcused`), a gdy ich brak — wnioskujemy
    ze słownikowej nazwy typu. Brak `PresenceType` traktujemy jako obecność: dopóki
    szkoła niczego nie odnotowała, nie ma czego usprawiedliwiać.
    """
    day = record_date(raw)
    if not day:
        return None
    slot = raw.get("TimeSlot") or {}
    pres = raw.get("PresenceType") or {}
    nazwa = (_name(pres) or "").strip()
    niska = nazwa.lower()

    absent = _flag(pres, "Absence")
    justified = _flag(pres, "AbsenceJustified", "Justified")
    late = _flag(pres, "Late", "Tardy")
    excused_late = _flag(pres, "LateExcused", "JustifiedLate")

    # Szkoły skracają nazwy typów ("nieob. uspraw."), więc dopasowujemy rdzenie, nie
    # pełne słowa, i odcinamy zaprzeczenie osobno — inaczej "uspraw." nie trafia w
    # "usprawiedliw" i usprawiedliwiona nieobecność ląduje na liście do załatwienia.
    uspr = ("uspraw" in niska or "justif" in niska) and not any(
        z in niska for z in ("nieuspraw", "nie uspraw", "unjustif")
    )
    if absent is None:
        absent = any(w in niska for w in ("nieobecn", "nieob", "absen"))
    if justified is None:
        justified = absent and uspr
    if late is None:
        late = any(w in niska for w in ("spóźn", "spozn", "late"))
    if excused_late is None:
        excused_late = late and uspr

    return Attendance(
        key=f"P{raw.get('Id')}-{day.isoformat()}",
        day=day,
        position=slot.get("Position"),
        subject=_name(raw.get("Subject")) or raw.get("Event") or "Zajęcia",
        kind=nazwa,
        present=not absent,
        absent=bool(absent),
        justified=bool(justified),
        late=bool(late),
        excused_late=bool(excused_late),
        lesson_class_id=raw.get("LessonClassId"),
        justification_pending=justification_pending(raw, bool(justified)),
        justification_status=justification_label(raw),
    )


def parse_note(raw: dict) -> Note:
    return Note(
        key=f"N{raw.get('Id')}",
        day=to_date(raw.get("ValidAt")),
        positive=bool(raw.get("Positive")),
        category=_name(raw.get("Category")),
        content=raw.get("Content") or "",
        teacher=_teacher(raw.get("Creator")),
    )


def parse_message(raw: dict) -> Message:
    return Message(
        key=str(raw.get("GlobalKey") or raw.get("Id")),
        thread_key=raw.get("ThreadKey"),
        subject=raw.get("Subject") or "",
        sender=_name(raw.get("Sender")),
        sent=to_datetime(raw.get("SentAt")),
        read=raw.get("ReadAt") is not None,
        content=raw.get("Content") or "",
    )


def parse_all(parser, items: list | None) -> list:
    out = []
    for item in items or []:
        if isinstance(item, dict):
            parsed = parser(item)
            if parsed is not None:
                out.append(parsed)
    return out


# --- wykrywanie nowości -------------------------------------------------------


def new_items(previous: set[str], items: list, key=lambda x: x.key) -> list:
    return [i for i in items if key(i) not in previous]


def lesson_change_key(lesson: Lesson) -> str:
    """Klucz zmiany w planie — nowe zastępstwo albo jego modyfikacja."""
    return f"{lesson.key}|{lesson.cancelled}|{lesson.subject}|{lesson.teacher}|{lesson.room}"


def window(today: date, back: int, ahead: int) -> tuple[date, date]:
    return today - timedelta(days=back), today + timedelta(days=ahead)
