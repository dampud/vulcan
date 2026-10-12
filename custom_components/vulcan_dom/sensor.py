"""Sensory ucznia: pierwsza lekcja, sprawdziany, oceny, wiadomości, zastępstwa, numerek."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import model as m
from .entity import VulcanEntity

MAX_LIST = 10


def _today():
    return dt_util.now().date()


def _lesson_attrs(lesson: m.Lesson | None) -> dict[str, Any]:
    if not lesson:
        return {}
    return {"przedmiot": lesson.subject, "sala": lesson.room, "nauczyciel": lesson.teacher,
            "lekcja": lesson.position, "zmiana": lesson.changed, "uwagi": lesson.change_note}


def _first_today(p: m.PupilData):
    return p.first_lesson(_today())


def _first_tomorrow(p: m.PupilData):
    return p.first_lesson(_today() + timedelta(days=1))


def _first_next_day(p: m.PupilData):
    day = p.next_school_day(_today())
    return p.first_lesson(day) if day else None


def _next_exam(p: m.PupilData):
    exams = p.upcoming_exams(_today())
    return exams[0] if exams else None


def _changes(p: m.PupilData) -> list[m.Lesson]:
    return p.changes_between(_today(), _today() + timedelta(days=7))


@dataclass(frozen=True, kw_only=True)
class VulcanSensorDescription(SensorEntityDescription):
    value: Callable[[m.PupilData], Any]
    attrs: Callable[[m.PupilData], dict[str, Any]] = lambda p: {}


SENSORS: tuple[VulcanSensorDescription, ...] = (
    VulcanSensorDescription(
        key="first_lesson_today", device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda p: (l.start if (l := _first_today(p)) else None),
        attrs=lambda p: _lesson_attrs(_first_today(p)),
    ),
    VulcanSensorDescription(
        key="first_lesson_tomorrow", device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda p: (l.start if (l := _first_tomorrow(p)) else None),
        attrs=lambda p: _lesson_attrs(_first_tomorrow(p)),
    ),
    VulcanSensorDescription(
        key="first_lesson_next_day", device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda p: (l.start if (l := _first_next_day(p)) else None),
        attrs=lambda p: _lesson_attrs(_first_next_day(p)),
    ),
    VulcanSensorDescription(
        key="next_exam", device_class=SensorDeviceClass.DATE,
        value=lambda p: (e.day if (e := _next_exam(p)) else None),
        attrs=lambda p: {
            "przedmiot": e.subject, "rodzaj": e.kind, "opis": e.content[:200],
            "wszystkie": [f"{x.day.isoformat()} {x.subject} ({x.kind})" for x in p.upcoming_exams(_today())[:MAX_LIST]],
        } if (e := _next_exam(p)) else {},
    ),
    VulcanSensorDescription(
        key="exams_7_days", native_unit_of_measurement="szt.",
        value=lambda p: sum(1 for e in p.upcoming_exams(_today()) if e.day <= _today() + timedelta(days=7)),
    ),
    VulcanSensorDescription(
        key="schedule_changes", native_unit_of_measurement="szt.",
        value=lambda p: len(_changes(p)),
        attrs=lambda p: {"zmiany": [
            f"{l.day.isoformat()} lekcja {l.position}: {'ODWOŁANA ' if l.cancelled else ''}{l.subject}"
            + (f" ({l.teacher})" if l.teacher else "") for l in _changes(p)[:MAX_LIST]
        ]},
    ),
    VulcanSensorDescription(
        key="last_grade",
        value=lambda p: (g.value if (g := p.latest_grade()) else None),
        attrs=lambda p: {"przedmiot": g.subject, "kolumna": g.column, "waga": g.weight,
                         "data": g.created.isoformat() if g.created else None} if (g := p.latest_grade()) else {},
    ),
    VulcanSensorDescription(
        key="unread_messages", native_unit_of_measurement="szt.",
        value=lambda p: p.unread_messages,
        attrs=lambda p: {"ostatnie": [
            f"{x.sent.strftime('%d.%m %H:%M') if x.sent else ''} {x.sender}: {x.subject}"
            for x in sorted((y for y in p.messages if not y.read), key=lambda y: y.sent or dt_util.utc_from_timestamp(0), reverse=True)[:MAX_LIST]
        ]},
    ),
    VulcanSensorDescription(
        key="notes", native_unit_of_measurement="szt.",
        value=lambda p: len(p.notes),
        attrs=lambda p: {"pozytywne": sum(1 for n in p.notes if n.positive),
                         "negatywne": sum(1 for n in p.notes if not n.positive)},
    ),
    VulcanSensorDescription(
        key="lucky_number",
        value=lambda p: p.lucky_number,
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coord = entry.runtime_data
    entities: list[SensorEntity] = []
    for login_id in coord.data:
        entities += [VulcanSensor(coord, login_id, d) for d in SENSORS]
        entities.append(VulcanLastSync(coord, login_id))
    async_add_entities(entities)


class VulcanSensor(VulcanEntity, SensorEntity):
    entity_description: VulcanSensorDescription

    def __init__(self, coordinator, login_id: int, description: VulcanSensorDescription) -> None:
        super().__init__(coordinator, login_id, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        return self.entity_description.value(self.pupil) if self.pupil else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.entity_description.attrs(self.pupil) if self.pupil else {}


class VulcanLastSync(VulcanEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, login_id: int) -> None:
        super().__init__(coordinator, login_id, "last_sync")

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self):
        return self.coordinator.last_sync

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        err = self.coordinator.last_exception
        return {"ok": self.coordinator.last_update_success, "błąd": str(err) if err else None}
