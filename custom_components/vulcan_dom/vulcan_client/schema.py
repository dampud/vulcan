"""Opis kształtu odpowiedzi API bez ujawniania treści.

Po to, żeby dało się sprawdzić na prawdziwym koncie, jakie pola przychodzą i w jakim
formacie (daty, zastępstwa, frekwencja), nie pokazując nikomu ani jednej oceny, uwagi
czy nazwiska. Zamiast wartości wypisujemy:

- ścieżkę pola i typ,
- ile rekordów je ma (i ile z nich ma `null`),
- maskę krótkich tekstów: cyfra → N, wielka litera → A, mała → a, reszta bez zmian,
  więc "2026-10-12 08:00:00" wychodzi jako "NNNN-NN-NN NN:NN:NN", a "Kowalski" jako
  "Aaaaaaaa".

Tekstów dłuższych niż MASK_LIMIT nie maskujemy wcale — podajemy sam typ i rząd
wielkości długości, bo maska akapitu to nadal jego kształt zdanie po zdaniu.
Konkretne wartości pokazuje wyłącznie `values_at()` dla ścieżki podanej z ręki.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

MASK_LIMIT = 40  # dłuższe teksty: tylko typ i długość
MAX_MASKS = 3  # ile różnych masek pokazać przy polu
ROOT = "[]"


def mask(value: str) -> str:
    return "".join(
        "N" if ch.isdigit() else "A" if ch.isupper() else "a" if ch.islower() else ch for ch in value
    )


def type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


@dataclass
class Field:
    """Jedno pole: gdzie występuje, jakie ma typy i jak wyglądają jego krótkie teksty."""

    path: str
    present: int = 0
    nulls: int = 0
    types: Counter = field(default_factory=Counter)
    masks: Counter = field(default_factory=Counter)
    lengths: list[int] = field(default_factory=list)

    def add(self, value: Any) -> None:
        self.present += 1
        self.types[type_name(value)] += 1
        if value is None:
            self.nulls += 1
        elif isinstance(value, str):
            self.lengths.append(len(value))
            if len(value) <= MASK_LIMIT:
                self.masks[mask(value)] += 1

    def describe(self, total: int) -> str:
        types = "|".join(t for t, _ in self.types.most_common())
        out = f"{self.path:<46} {types:<12} {self.present}/{total}"
        if self.nulls:
            out += f" null:{self.nulls}"
        if self.masks:
            shapes = ", ".join(s for s, _ in self.masks.most_common(MAX_MASKS))
            more = "…" if len(self.masks) > MAX_MASKS else ""
            out += f"  {shapes}{more}"
        elif self.lengths:
            out += f"  tekst {min(self.lengths)}–{max(self.lengths)} zn."
        return out


def walk(value: Any, path: str, fields: dict[str, Field]) -> None:
    """Rejestruje pole i schodzi w głąb. Listy opisujemy po elementach, nie po indeksach."""
    fields.setdefault(path, Field(path)).add(value)
    if isinstance(value, dict):
        for key, sub in sorted(value.items()):
            walk(sub, f"{path}.{key}", fields)
    elif isinstance(value, list):
        for item in value:
            walk(item, f"{path}[]", fields)


def summarize(records: Any) -> tuple[int, list[Field]]:
    """Zwraca (liczba rekordów, pola posortowane po ścieżce)."""
    items = records if isinstance(records, list) else [records]
    fields: dict[str, Field] = {}
    for item in items:
        walk(item, ROOT, fields)
    ordered = sorted((f for p, f in fields.items() if p != ROOT), key=lambda f: f.path)
    return len(items), ordered


def render(kind: str, records: Any) -> str:
    total, fields = summarize(records)
    lines = [f"{kind}: rekordów {total}", ""]
    lines += [f.describe(total) for f in fields]
    return "\n".join(lines)


def values_at(records: Any, path: str) -> Counter:
    """Rozkład wartości dokładnie jednej ścieżki — tylko gdy ktoś wprost o nią poprosi.

    Ścieżka jak w wydruku, np. '[].PresenceType.Name'. Służy do słowników
    (rodzaje frekwencji, typy sprawdzianów), nie do treści.
    """
    items = records if isinstance(records, list) else [records]
    found: Counter = Counter()

    def dig(value: Any, rest: list[str]) -> None:
        if not rest:
            found[repr(value) if not isinstance(value, (dict, list)) else type_name(value)] += 1
            return
        head, tail = rest[0], rest[1:]
        if head == "[]":
            if isinstance(value, list):
                for sub in value:
                    dig(sub, tail)
        elif isinstance(value, dict) and head in value:
            dig(value[head], tail)

    parts = [p for p in path.replace("[]", ".[]").split(".") if p]
    for item in items:
        dig(item, parts[1:] if parts and parts[0] == "[]" else parts)
    return found
