"""Kalendarze ucznia: plan lekcji (z zastępstwami) oraz sprawdziany i zadania."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import model as m
from .entity import VulcanEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coord = entry.runtime_data
    entities = []
    for pupil_id in coord.data:
        entities += [LessonsCalendar(coord, pupil_id, "lessons"), DutiesCalendar(coord, pupil_id, "duties")]
    async_add_entities(entities)


def _lesson_event(l: m.Lesson) -> CalendarEvent:
    prefix = "ODWOŁANA: " if l.cancelled else ("Zmiana: " if l.changed else "")
    desc = "\n".join(filter(None, [
        f"Nauczyciel: {l.teacher}" if l.teacher else None,
        f"Grupa: {l.group}" if l.group else None,
        l.change_note,
    ]))
    return CalendarEvent(start=l.start, end=l.end, summary=f"{prefix}{l.position or ''} {l.subject}".strip(),
                         location=l.room, description=desc or None, uid=l.key)


def _duty_events(p: m.PupilData) -> list[CalendarEvent]:
    events = [
        CalendarEvent(start=e.day, end=e.day + timedelta(days=1), summary=f"{e.kind.capitalize()}: {e.subject}",
                      description=e.content or None, uid=e.key)
        for e in p.exams
    ]
    events += [
        CalendarEvent(start=h.day, end=h.day + timedelta(days=1), summary=f"Zadanie: {h.subject}",
                      description=h.content or None, uid=h.key)
        for h in p.homework
    ]
    return events


def _in_range(ev: CalendarEvent, start: datetime, end: datetime) -> bool:
    return ev.start_datetime_local < end and ev.end_datetime_local > start


class LessonsCalendar(VulcanEntity, CalendarEntity):
    def _events(self) -> list[CalendarEvent]:
        return [_lesson_event(l) for l in self.pupil.lessons] if self.pupil else []

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        upcoming = sorted((e for e in self._events() if e.end_datetime_local > now and not e.summary.startswith("ODWOŁANA")),
                          key=lambda e: e.start_datetime_local)
        return upcoming[0] if upcoming else None

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        return [e for e in self._events() if _in_range(e, start_date, end_date)]


class DutiesCalendar(VulcanEntity, CalendarEntity):
    def _events(self) -> list[CalendarEvent]:
        return _duty_events(self.pupil) if self.pupil else []

    @property
    def event(self) -> CalendarEvent | None:
        now = dt_util.now()
        upcoming = sorted((e for e in self._events() if e.end_datetime_local > now), key=lambda e: e.start_datetime_local)
        return upcoming[0] if upcoming else None

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        return [e for e in self._events() if _in_range(e, start_date, end_date)]
