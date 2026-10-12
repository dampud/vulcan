"""Koordynator: cykliczne pobieranie danych ucznia, wykrywanie nowości, zdarzenia HA."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import model as m
from .const import (
    CONF_QUIET_END,
    CONF_QUIET_START,
    CONF_SCAN_INTERVAL,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_START,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT,
    EVENT_TEXT_LIMIT,
    WINDOW_EXAMS,
    WINDOW_HOMEWORK,
    WINDOW_SCHEDULE,
)
from .vulcan_client import ApiError, AuthError, TransportError, VulcanApi

_LOGGER = logging.getLogger(__name__)

CATEGORIES = ("grades", "notes", "messages", "exams", "homework", "changes")


def _short(text: str | None) -> str:
    text = (text or "").strip()
    return text if len(text) <= EVENT_TEXT_LIMIT else text[: EVENT_TEXT_LIMIT - 1] + "…"


class VulcanCoordinator(DataUpdateCoordinator[dict[int, m.PupilData]]):
    """Dane wszystkich uczniów z jednego konta (klucz: LoginId)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: VulcanApi) -> None:
        minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(minutes=minutes),
        )
        self.api = api
        self.accounts: list[dict] = []
        self._store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.seen")
        self._seen: dict[str, dict[str, list[str]]] | None = None
        self.last_sync = None
        self.force_next = False

    # --- cisza nocna ---------------------------------------------------------

    def _quiet_now(self) -> bool:
        opts = self.config_entry.options
        start = opts.get(CONF_QUIET_START, DEFAULT_QUIET_START)
        end = opts.get(CONF_QUIET_END, DEFAULT_QUIET_END)
        hour = dt_util.now().hour
        if start == end:
            return False
        return (start <= hour or hour < end) if start > end else (start <= hour < end)

    # --- pobieranie ----------------------------------------------------------

    async def _async_update_data(self) -> dict[int, m.PupilData]:
        if self.data and self._quiet_now() and not self.force_next:
            return self.data
        self.force_next = False
        try:
            self.accounts = await self.api.accounts()
            pupils = await asyncio.gather(*(self._fetch_pupil(acc) for acc in self.accounts))
        except AuthError as err:
            raise ConfigEntryAuthFailed(f"urządzenie odrzucone przez eduVULCAN: {err}") from err
        except (TransportError, ApiError) as err:
            raise UpdateFailed(str(err)) from err
        data = {p.login_id: p for p in pupils}
        self.last_sync = dt_util.utcnow()
        await self._detect_changes(data)
        return data

    async def _fetch_pupil(self, acc: dict) -> m.PupilData:
        rest = acc["Unit"]["RestURL"]
        pupil = acc["Pupil"]
        pid = pupil["Id"]
        today = dt_util.now().date()
        box = (acc.get("MessageBox") or {}).get("GlobalKey")
        period = next((p for p in acc.get("Periods") or [] if p.get("Current")), None)

        s_from, s_to = m.window(today, *WINDOW_SCHEDULE)
        e_from, e_to = m.window(today, *WINDOW_EXAMS)
        h_from, h_to = m.window(today, *WINDOW_HOMEWORK)

        async def none():
            return None

        schedule, exams, homework, grades, notes, messages = await asyncio.gather(
            self.api.schedule(rest, pid, s_from, s_to),
            self.api.exams(rest, pid, e_from, e_to),
            self.api.homework(rest, pid, h_from, h_to),
            self.api.grades(rest, pid, acc["Unit"]["Id"], period["Id"]) if period else none(),
            self.api.notes(rest, pid),
            self.api.messages_received(rest, pid, box) if box else none(),
        )
        lucky = None
        try:
            raw = await self.api.lucky_number(rest, pid, acc["ConstituentUnit"]["Id"], today)
            lucky = (raw or {}).get("Number") or None
        except (ApiError, TransportError):
            pass  # szkoła może nie losować numerka

        return m.PupilData(
            pupil_id=pid,
            login_id=pupil["LoginId"],
            name=f"{pupil.get('FirstName', '')} {pupil.get('Surname', '')}".strip(),
            lessons=m.parse_all(m.parse_lesson, schedule),
            exams=m.parse_all(m.parse_exam, exams),
            homework=m.parse_all(m.parse_homework, homework),
            grades=m.parse_all(m.parse_grade, grades),
            notes=m.parse_all(m.parse_note, notes),
            messages=m.parse_all(m.parse_message, messages),
            lucky_number=lucky,
        )

    def account_for(self, login_id: int) -> dict:
        return next(a for a in self.accounts if a["Pupil"]["LoginId"] == login_id)

    # --- nowości → zdarzenia -------------------------------------------------

    async def _detect_changes(self, data: dict[int, m.PupilData]) -> None:
        if self._seen is None:
            self._seen = await self._store.async_load() or {}
        for login_id, pupil in data.items():
            seen = self._seen.setdefault(str(login_id), {})
            current = {
                "grades": {g.key: g for g in pupil.grades},
                "notes": {n.key: n for n in pupil.notes},
                "messages": {x.key: x for x in pupil.messages},
                "exams": {e.key: e for e in pupil.exams},
                "homework": {h.key: h for h in pupil.homework},
                "changes": {m.lesson_change_key(l): l for l in pupil.lessons if l.changed or l.cancelled},
            }
            for cat in CATEGORIES:
                keys = current[cat]
                if cat in seen:  # pierwsze pobranie kategorii = stan bazowy, bez zdarzeń
                    known = set(seen[cat])
                    for key, item in keys.items():
                        if key not in known:
                            self._fire(cat, pupil, item)
                # trzymamy klucze z bieżącego okna + poprzednie (bez puchnięcia)
                seen[cat] = sorted(set(keys) | set(seen.get(cat, [])[-2000:]))
        await self._store.async_save(self._seen)

    def _fire(self, cat: str, pupil: m.PupilData, item) -> None:
        base = {"pupil": pupil.name, "login_id": pupil.login_id}
        if cat == "grades":
            data = {"type": "new_grade", "subject": item.subject, "grade": item.value,
                    "column": item.column, "weight": item.weight, "teacher": item.teacher}
        elif cat == "notes":
            data = {"type": "new_note", "positive": item.positive, "category": item.category,
                    "content": _short(item.content), "teacher": item.teacher,
                    "date": item.day.isoformat() if item.day else None}
        elif cat == "messages":
            data = {"type": "new_message", "subject": item.subject, "sender": item.sender,
                    "content": _short(item.content), "message_key": item.key,
                    "sent": item.sent.isoformat() if item.sent else None}
        elif cat == "exams":
            data = {"type": "new_exam", "subject": item.subject, "kind": item.kind,
                    "content": _short(item.content), "date": item.day.isoformat()}
        elif cat == "homework":
            data = {"type": "new_homework", "subject": item.subject,
                    "content": _short(item.content), "date": item.day.isoformat()}
        else:
            data = {"type": "schedule_change", "subject": item.subject, "date": item.day.isoformat(),
                    "lesson": item.position, "start": item.start.isoformat(), "cancelled": item.cancelled,
                    "teacher": item.teacher, "room": item.room, "note": item.change_note}
        self.hass.bus.async_fire(EVENT, {**base, **data})
