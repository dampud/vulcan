"""Klient API mobilnego eduVULCAN (Hebe CE).

Endpointy odczytu za iris (bbrjpl1310b/iris, AGPL-3.0). Zapisy (wiadomość,
usprawiedliwienie) za eduvulcan-clone / Vulcanova / DzienniczekSzpontniczek —
wymagają usługi rozszerzonej na koncie.

Odpowiedzi zwracamy jako surowe dict/list (pola jak w API, PascalCase) —
modele dokładamy, gdy zobaczymy realne dane.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import aiohttp

from .credential import Credential
from .http import BASE_URL, HttpClient

EPOCH = datetime(1970, 1, 1, 1, 0, 0)
INT_MIN = -2_147_483_648
PAGE = 500
MAX_PAGES = 40  # bezpiecznik: 40 × 500 = 20 000 rekordów na jedno pobranie


def _sync(**params: Any) -> dict[str, Any]:
    """Parametry pełnej synchronizacji (jak aplikacja przy pierwszym pobraniu)."""
    return {**params, "lastSyncDate": EPOCH, "lastId": INT_MIN, "pageSize": PAGE}


class VulcanApi:
    def __init__(self, credential: Credential, session: aiohttp.ClientSession | None = None):
        self.credential = credential
        self.http = HttpClient(credential, session)

    async def close(self) -> None:
        await self.http.close()

    async def __aenter__(self) -> "VulcanApi":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # --- rejestracja / konta ---------------------------------------------

    async def register_jwt(self, tokens: list[str], tenant: str) -> str:
        """Rejestruje to urządzenie dla tokenów JWT z eduvulcan.pl/api/ap (jeden tenant)."""
        rest_url = f"{BASE_URL}/{tenant}/api"
        await self.http.request(
            "POST",
            "mobile/register/jwt",
            rest_url,
            payload={
                "OS": self.credential.device_os,
                "Certificate": self.credential.certificate,
                "CertificateType": self.credential.type,
                "DeviceModel": self.credential.device_model,
                "SelfIdentifier": self.credential.device_id,
                "CertificateThumbprint": self.credential.fingerprint,
                "Tokens": tokens,
            },
        )
        self.credential.rest_url = rest_url
        return rest_url

    async def accounts(self) -> list[dict]:
        return await self.http.request("GET", "mobile/register/hebe", query={"mode": 2})

    async def unregister(self) -> None:
        """Wyrejestrowuje to urządzenie (certyfikat przestaje działać)."""
        await self.http.request("DELETE", "mobile/register")

    # --- odczyt (rest_url = account["Unit"]["RestURL"]) -------------------

    async def _get(self, rest_url: str, endpoint: str, pupil_id: int, **query: Any) -> Any:
        return await self.http.request("GET", endpoint, rest_url, pupil_id=pupil_id, query=query)

    async def _get_paged(
        self, rest_url: str, endpoint: str, pupil_id: int, max_pages: int | None = None, **query: Any
    ) -> list[dict]:
        """Pobiera wszystkie strony.

        Hebe tnie odpowiedź do pageSize i nie mówi, że coś zostało — kolejną stronę
        bierze się podając `lastId` = największe Id z poprzedniej. Pętla kończy się na
        krótkiej stronie, na braku nowych rekordów albo na bezpieczniku MAX_PAGES
        (gdyby serwer ignorował lastId i w kółko oddawał to samo).

        `max_pages` obniża ten bezpiecznik dla wywołań, które muszą się zmieścić w
        czasie — każda strona to osobne żądanie z własnym timeoutem, więc domyślne
        40 stron potrafi w najgorszym razie zająć kwadranse.
        """
        page_size = int(query.get("pageSize") or PAGE)
        last_id = query.get("lastId", INT_MIN)
        out: list[dict] = []
        seen: set[Any] = set()
        for _ in range(min(max_pages or MAX_PAGES, MAX_PAGES)):
            page = await self._get(rest_url, endpoint, pupil_id, **{**query, "lastId": last_id})
            if not isinstance(page, list) or not page:
                break
            fresh = [r for r in page if isinstance(r, dict) and r.get("Id") not in seen]
            if not fresh:
                break
            out.extend(fresh)
            seen.update(r.get("Id") for r in page if isinstance(r, dict))
            ids = [r["Id"] for r in page if isinstance(r, dict) and isinstance(r.get("Id"), int)]
            if len(page) < page_size or not ids:
                break
            nxt = max(ids)
            if nxt == last_id:
                break
            last_id = nxt
        return out

    async def schedule(self, rest_url: str, pupil_id: int, date_from: date, date_to: date) -> list[dict]:
        """Plan z zastępstwami."""
        return await self._get_paged(
            rest_url, "mobile/schedule/withchanges/byPupil", pupil_id,
            **_sync(pupilId=pupil_id, dateFrom=date_from, dateTo=date_to),
        )

    async def exams(self, rest_url: str, pupil_id: int, date_from: date, date_to: date) -> list[dict]:
        return await self._get_paged(
            rest_url, "mobile/exam/byPupil", pupil_id,
            **_sync(pupilId=pupil_id, dateFrom=date_from, dateTo=date_to),
        )

    async def homework(self, rest_url: str, pupil_id: int, date_from: date, date_to: date) -> list[dict]:
        return await self._get_paged(
            rest_url, "mobile/homework/byPupil", pupil_id,
            **_sync(pupilId=pupil_id, dateFrom=date_from, dateTo=date_to),
        )

    async def grades(self, rest_url: str, pupil_id: int, unit_id: int, period_id: int) -> list[dict]:
        return await self._get_paged(
            rest_url, "mobile/grade/byPupil", pupil_id,
            **_sync(unitId=unit_id, pupilId=pupil_id, periodId=period_id),
        )

    async def notes(self, rest_url: str, pupil_id: int) -> list[dict]:
        """Uwagi i pochwały."""
        return await self._get_paged(rest_url, "mobile/note/byPupil", pupil_id, **_sync(pupilId=pupil_id))

    async def lessons(self, rest_url: str, pupil_id: int, date_from: date, date_to: date) -> list[dict]:
        """Lekcje zrealizowane z frekwencją; źródło LessonClassId do usprawiedliwień."""
        return await self._get_paged(
            rest_url, "mobile/lesson/byPupil", pupil_id,
            **_sync(pupilId=pupil_id, dateFrom=date_from, dateTo=date_to),
        )

    async def lucky_number(self, rest_url: str, pupil_id: int, constituent_id: int, day: date) -> dict:
        return await self._get(
            rest_url, "mobile/school/lucky", pupil_id,
            pupilId=pupil_id, constituentId=constituent_id, day=day,
        )

    async def vacations(self, rest_url: str, pupil_id: int, date_from: date, date_to: date) -> list[dict]:
        return await self._get_paged(
            rest_url, "mobile/school/vacation", pupil_id,
            **_sync(pupilId=pupil_id, dateFrom=date_from, dateTo=date_to),
        )

    async def messages_received(
        self,
        rest_url: str,
        pupil_id: int,
        box: str,
        since: datetime | None = None,
        max_pages: int | None = None,
    ) -> list[dict]:
        """Odebrane wiadomości.

        `since` ogranicza odpowiedź do rekordów zmienionych po tej dacie (czas lokalny
        szkoły) — skrzynka potrafi mieć tysiące wiadomości i pełne pobieranie co kwadrans
        nie ma sensu. Bez `since` pobiera całość, stronicując; wywołujący powinien wtedy
        podać `max_pages`, żeby pobranie nie rozciągnęło się w nieskończoność.
        """
        return await self._get_paged(
            rest_url, "mobile/messages/received/byBox", pupil_id,
            max_pages=max_pages,
            **{**_sync(box=box, pupilId=pupil_id), "lastSyncDate": since or EPOCH},
        )

    async def messages_sent(self, rest_url: str, pupil_id: int, box: str) -> list[dict]:
        return await self._get_paged(
            rest_url, "mobile/messages/sent/byBox", pupil_id, **_sync(box=box, pupilId=pupil_id)
        )

    async def addressbook(self, rest_url: str, pupil_id: int, box: str) -> list[dict]:
        """Lista adresatów dla skrzynki (GlobalKey + Name)."""
        return await self._get(rest_url, "mobile/addressbook", pupil_id, box=box)

    # --- zapis (usługa rozszerzona) ---------------------------------------

    @staticmethod
    def message_payload(
        box_key: str,
        sender_name: str,
        receivers: list[dict],
        subject: str,
        content: str,
        thread_key: str | None = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "BoxKey": box_key,
            "Subject": subject,
            "Content": content,
            "Sender": {"GlobalKey": box_key, "Name": sender_name},
            "Receiver": [{"GlobalKey": r["GlobalKey"], "Name": r["Name"]} for r in receivers],
        }
        if thread_key:
            payload["ThreadKey"] = thread_key
        return payload

    async def send_message(self, rest_url: str, pupil_id: int, payload: dict) -> Any:
        """Wysyła wiadomość. Payload z message_payload(); wywołujący odpowiada za potwierdzenie."""
        return await self.http.request("POST", "mobile/messages", rest_url, pupil_id=pupil_id, payload=payload)

    @staticmethod
    def justification_payload(pupil_id: int, login_id: int, lesson_class_id: int, reason: str) -> dict:
        return {
            "Reason": reason,
            "LessonClassId": lesson_class_id,
            "PupilId": pupil_id,
            "LoginId": login_id,
        }

    async def justify_lesson(self, rest_url: str, pupil_id: int, payload: dict) -> Any:
        """Usprawiedliwia jedną lekcję. Cały dzień = pętla po lekcjach z lessons()."""
        return await self.http.request(
            "POST", "mobile/presence/justification/lesson", rest_url, pupil_id=pupil_id, payload=payload
        )
