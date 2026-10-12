"""Dane syntetyczne — zmyślona szkoła, zmyśleni ludzie, kształt pól jak w Hebe.

Żadnego fragmentu prawdziwej odpowiedzi API. Daty są względem DZIS, żeby testy
nie zgniły wraz z kalendarzem; czas w testach i tak jest zamrożony na DZIS 06:30.
"""

from __future__ import annotations

from datetime import date, timedelta

TENANT = "testowo"
REST = f"https://lekcjaplus.vulcan.net.pl/{TENANT}/api"
BOX = "box-testowy"
PUPIL_ID = 101
LOGIN_ID = 9001
UNIT_ID = 7
CONSTITUENT_ID = 77
PERIOD_ID = 11

DZIS = date(2026, 10, 12)  # poniedziałek
JUTRO = DZIS + timedelta(days=1)
POJUTRZE = DZIS + timedelta(days=2)


def iso(day: date) -> str:
    return day.isoformat()


ACCOUNT = {
    "Pupil": {"Id": PUPIL_ID, "LoginId": LOGIN_ID, "FirstName": "Ala", "Surname": "Testowa"},
    "Unit": {"Id": UNIT_ID, "RestURL": REST, "Name": "Szkoła Testowa nr 1"},
    "ConstituentUnit": {"Id": CONSTITUENT_ID, "Name": "Szkoła Testowa nr 1"},
    "MessageBox": {"GlobalKey": BOX, "Name": "Rodzic Testowy"},
    "Periods": [{"Id": PERIOD_ID, "Number": 1, "Current": True}],
    "ClassDisplay": "5a",
    "Capabilities": ["EDUVULCAN_PREMIUM", "JUSTIFICATIONS_ENABLED"],
    "State": 1,
}


def slot(position: int, start: str, end: str) -> dict:
    return {"Id": position, "Position": position, "Start": start, "End": end}


SCHEDULE = [
    {
        "Id": 1, "DateAt": iso(DZIS), "TimeSlot": slot(1, "08:00:00", "08:45:00"),
        "Subject": {"Id": 1, "Name": "Matematyka", "Kod": "mat"},
        "TeacherPrimary": {"Id": 1, "Name": "Jan", "Surname": "Nowakowy", "DisplayName": "Jan Nowakowy"},
        "Room": {"Id": 1, "Code": "12"}, "Distribution": None, "Substitution": None,
    },
    {
        "Id": 2, "DateAt": iso(DZIS), "TimeSlot": slot(2, "08:55:00", "09:40:00"),
        "Subject": {"Id": 2, "Name": "Biologia"},
        "TeacherPrimary": {"Id": 2, "DisplayName": "Ewa Przykładowa"},
        "Room": {"Id": 2, "Code": "7"}, "Distribution": {"Name": "gr. 1"},
        "Substitution": {
            "Id": 51, "ChangeDateAt": iso(DZIS), "TimeSlot": slot(2, "08:55:00", "09:40:00"),
            "Subject": {"Id": 3, "Name": "Chemia"},
            "TeacherPrimary": {"Id": 3, "DisplayName": "Piotr Zastępczy"},
            "Room": {"Id": 3, "Code": "21"}, "Reason": "zastępstwo",
            "ClassAbsence": False, "PupilNote": None, "Description": None,
        },
    },
    {
        "Id": 3, "DateAt": iso(DZIS), "TimeSlot": slot(3, "09:50:00", "10:35:00"),
        "Subject": {"Id": 4, "Name": "Historia"},
        "TeacherPrimary": {"Id": 4, "DisplayName": "Anna Odwołana"},
        "Room": {"Id": 4, "Code": "3"}, "Distribution": None,
        "Substitution": {
            "Id": 52, "ChangeDateAt": iso(DZIS), "TimeSlot": slot(3, "09:50:00", "10:35:00"),
            "Subject": None, "TeacherPrimary": None, "Room": None,
            "ClassAbsence": True, "Reason": "wycieczka klasy", "PupilNote": None, "Description": None,
        },
    },
    {
        "Id": 4, "DateAt": iso(JUTRO), "TimeSlot": slot(1, "09:00:00", "09:45:00"),
        "Subject": {"Id": 5, "Name": "Polski"},
        "TeacherPrimary": {"Id": 5, "DisplayName": "Maria Polonistka"},
        "Room": {"Id": 5, "Code": "1"}, "Distribution": None, "Substitution": None,
    },
    {
        "Id": 5, "DateAt": iso(POJUTRZE), "TimeSlot": slot(1, "08:00:00", "08:45:00"),
        "Subject": {"Id": 6, "Name": "Fizyka"},
        "TeacherPrimary": {"Id": 6, "DisplayName": "Karol Fizyk"},
        "Room": {"Id": 6, "Code": "9"}, "Distribution": None, "Substitution": None,
    },
]

EXAMS = [
    {"Id": 11, "DeadlineAt": iso(DZIS + timedelta(days=3)), "Subject": {"Name": "Matematyka"},
     "Type": "Sprawdzian", "Content": "Ułamki zwykłe", "Creator": {"DisplayName": "Jan Nowakowy"}},
    {"Id": 12, "DeadlineAt": iso(DZIS + timedelta(days=30)), "Subject": {"Name": "Biologia"},
     "Type": "Kartkówka", "Content": "Komórka", "Creator": {"DisplayName": "Ewa Przykładowa"}},
]

HOMEWORK = [
    {"Id": 21, "DeadlineAt": iso(DZIS + timedelta(days=2)), "Subject": {"Name": "Polski"},
     "Content": "Czytanie lektury, rozdziały 1-3", "Creator": {"DisplayName": "Maria Polonistka"}},
]

GRADES = [
    {"Id": 31, "Content": "4", "ContentRaw": "4", "CreatedAt": f"{iso(DZIS - timedelta(days=5))} 10:00:00",
     "ModifiedAt": f"{iso(DZIS - timedelta(days=5))} 10:00:00",
     "Column": {"Name": "Sprawdzian", "Code": "spr", "Weight": 3.0, "Subject": {"Name": "Matematyka"}},
     "Creator": {"DisplayName": "Jan Nowakowy"}},
    {"Id": 32, "Content": "5", "ContentRaw": "5", "CreatedAt": f"{iso(DZIS - timedelta(days=1))} 12:30:00",
     "ModifiedAt": f"{iso(DZIS - timedelta(days=1))} 12:30:00",
     "Column": {"Name": "Odpowiedź", "Code": "odp", "Weight": 1.0, "Subject": {"Name": "Biologia"}},
     "Creator": {"DisplayName": "Ewa Przykładowa"}},
    # ocena z plusem bez pola Value — wartość liczymy z tekstu (5 + 0,5)
    {"Id": 33, "Content": "5+", "ContentRaw": "5+", "CreatedAt": f"{iso(DZIS - timedelta(days=4))} 09:00:00",
     "ModifiedAt": f"{iso(DZIS - timedelta(days=4))} 09:00:00",
     "Column": {"Name": "Kartkówka", "Code": "kar", "Weight": 2.0, "Subject": {"Name": "Matematyka"}},
     "Creator": {"DisplayName": "Jan Nowakowy"}},
    # serwer podaje własną wartość — ma pierwszeństwo przed naszym liczeniem minusa
    {"Id": 34, "Content": "3-", "ContentRaw": "3-", "Value": 2.9,
     "CreatedAt": f"{iso(DZIS - timedelta(days=3))} 11:00:00",
     "ModifiedAt": f"{iso(DZIS - timedelta(days=3))} 11:00:00",
     "Column": {"Name": "Odpowiedź", "Code": "odp", "Weight": 1.0, "Subject": {"Name": "Biologia"}},
     "Creator": {"DisplayName": "Ewa Przykładowa"}},
    # wpis bez wartości liczbowej — widoczny na liście, poza średnią
    {"Id": 35, "Content": "np", "ContentRaw": "np", "CreatedAt": f"{iso(DZIS - timedelta(days=6))} 08:10:00",
     "ModifiedAt": f"{iso(DZIS - timedelta(days=6))} 08:10:00",
     "Column": {"Name": "Nieprzygotowanie", "Code": "np", "Weight": 0.0, "Subject": {"Name": "Matematyka"}},
     "Creator": {"DisplayName": "Jan Nowakowy"}},
]

NOTES = [
    {"Id": 41, "ValidAt": iso(DZIS - timedelta(days=2)), "Positive": True,
     "Category": {"Name": "Pomoc koleżeńska"}, "Content": "Pomogła młodszym na przerwie",
     "Creator": {"DisplayName": "Anna Wychowawczyni"}},
    {"Id": 42, "ValidAt": iso(DZIS - timedelta(days=10)), "Positive": False,
     "Category": {"Name": "Spóźnienie"}, "Content": "Spóźnienie na pierwszą lekcję",
     "Creator": {"DisplayName": "Jan Nowakowy"}},
]


def message(id_: int, subject: str, read: bool, days_ago: int) -> dict:
    sent = f"{iso(DZIS - timedelta(days=days_ago))} 15:00:00"
    return {
        "Id": id_, "GlobalKey": f"msg-{id_}", "ThreadKey": f"thr-{id_}", "Subject": subject,
        "Sender": {"GlobalKey": "t-1", "Name": "Jan Nowakowy"}, "Content": f"Treść wiadomości {id_}",
        "SentAt": sent, "DateModify": sent, "ReadAt": f"{iso(DZIS)} 08:00:00" if read else None,
    }


MESSAGES = [
    message(61, "Zebranie", True, 10),
    message(62, "Wycieczka", True, 3),
    message(63, "Prośba o kontakt", False, 1),
]

ADDRESSBOOK = [
    {"GlobalKey": "t-1", "Name": "Jan Nowakowy"},
    {"GlobalKey": "t-2", "Name": "Ewa Przykładowa"},
    {"GlobalKey": "t-3", "Name": "Maria Polonistka"},
]

LUCKY = {"Number": 13, "Day": iso(DZIS)}

# lekcje zrealizowane — źródło LessonClassId i frekwencji dla usprawiedliwień
LESSONS = [
    {"Id": 71, "LessonClassId": 701, "DateAt": iso(DZIS - timedelta(days=1)),
     "TimeSlot": slot(1, "08:00:00", "08:45:00"), "Subject": {"Name": "Matematyka"},
     "PresenceType": {"Id": 1, "Name": "Nieobecność", "Absence": True, "AbsenceJustified": False,
                      "Symbol": "n", "CategoryId": 2}},
    {"Id": 72, "LessonClassId": 702, "DateAt": iso(DZIS - timedelta(days=1)),
     "TimeSlot": slot(2, "08:55:00", "09:40:00"), "Subject": {"Name": "Biologia"},
     "PresenceType": {"Id": 1, "Name": "Nieobecność", "Absence": True, "AbsenceJustified": False,
                      "Symbol": "n", "CategoryId": 2}},
    {"Id": 73, "LessonClassId": 703, "DateAt": iso(DZIS - timedelta(days=1)),
     "TimeSlot": slot(3, "09:50:00", "10:35:00"), "Subject": {"Name": "Historia"},
     "PresenceType": {"Id": 2, "Name": "Obecność", "Absence": False, "AbsenceJustified": False,
                      "Symbol": "", "CategoryId": 1}},
]


def ap_payload(tenant: str = TENANT, tokens: int = 1) -> dict:
    """JSON jak z eduvulcan.pl/api/ap (tokeny zmyślone, podpis nieprawdziwy)."""
    import base64
    import json

    def b64(obj: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    jwt = f"{b64({'alg': 'none'})}.{b64({'tenant': tenant, 'name': 'Ala Testowa'})}.podpis"
    return {"Success": True, "IsConsentAccepted": True, "ErrorMessage": None, "Tokens": [jwt] * tokens}
