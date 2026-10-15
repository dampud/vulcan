"""CLI do testów klienta poza Home Assistantem.

  vulcan register [PLIK|-]     rejestracja urządzenia z JSON-a z eduvulcan.pl/api/ap
  vulcan accounts              uczniowie, szkoła, uprawnienia (Capabilities)
  vulcan fetch RODZAJ          surowy JSON: schedule|exams|homework|grades|notes|lessons|
                               messages|addressbook|lucky|vacations
  vulcan schema RODZAJ         same pola, typy i maski dat — bez treści
  vulcan parse RODZAJ          ile rekordów rozpoznaje parser integracji — bez treści
  vulcan fixture RODZAJ        zamaskowane rekordy do testów (bez treści dziennika)
  vulcan send-message ...      podgląd treści; wysyłka dopiero z --send
  vulcan justify ...           podgląd; wysyłka dopiero z --send
  vulcan unregister            wyrejestrowanie urządzenia (z --yes)

Zakres dni: --back/--ahead liczone od dziś albo wprost --from/--to (RRRR-MM-DD).

Plik z kluczem: $VULCAN_CREDENTIAL albo ~/.config/vulcan/credential.json (0600).
Nic z tego pliku nie trafia na wyjście.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from . import schema
from .api import VulcanApi
from .auth import ApDataError
from .auth import parse_ap as _parse_ap
from .credential import Credential
from .errors import VulcanError

DEFAULT_CRED = Path(os.environ.get("VULCAN_CREDENTIAL", "~/.config/vulcan/credential.json")).expanduser()


def parse_ap(raw: str) -> dict[str, list[str]]:
    try:
        return _parse_ap(raw)
    except ApDataError as err:
        raise SystemExit(f"/api/ap: {err}") from None


def pupil_label(acc: dict) -> str:
    p = acc.get("Pupil") or {}
    return f"{p.get('FirstName', '?')} {p.get('Surname', '?')}"


def pick(accounts: list[dict], pupil: int | None) -> dict:
    if not accounts:
        raise SystemExit("brak kont")
    if pupil is None:
        if len(accounts) > 1:
            raise SystemExit("kilku uczniów — podaj --pupil (indeks z `vulcan accounts`)")
        return accounts[0]
    return accounts[pupil]


def dump(obj: Any) -> None:
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")


async def cmd_register(args: argparse.Namespace) -> None:
    if args.credential.exists() and not args.force:
        raise SystemExit(f"{args.credential} istnieje — użyj --force, by zarejestrować nowe urządzenie")
    raw = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    by_tenant = parse_ap(raw)
    if len(by_tenant) > 1:
        raise SystemExit(f"tokeny z {len(by_tenant)} jednostek — obsługa wielu jednostek jeszcze nie zrobiona")
    tenant, tokens = next(iter(by_tenant.items()))
    cred = Credential.create(device_model=args.device_model)
    async with VulcanApi(cred) as api:
        await api.register_jwt(tokens, tenant)
        cred.save(args.credential)
        accounts = await api.accounts()
    print(f"zarejestrowano urządzenie dla jednostki '{tenant}', uczniów: {len(accounts)}; klucz: {args.credential}")


async def cmd_accounts(args: argparse.Namespace) -> None:
    async with VulcanApi(Credential.load(args.credential)) as api:
        accounts = await api.accounts()
    for i, acc in enumerate(accounts):
        unit = acc.get("Unit") or {}
        print(f"[{i}] {pupil_label(acc)} | klasa {acc.get('ClassDisplay')} | {unit.get('Name')}")
        print(f"    PupilId={acc['Pupil']['Id']} LoginId={acc['Pupil'].get('LoginId')} "
              f"skrzynka={'tak' if acc.get('MessageBox') else 'nie'} State={acc.get('State')}")
        print(f"    Capabilities: {', '.join(acc.get('Capabilities') or []) or '(brak)'}")
        current = [p for p in acc.get("Periods") or [] if p.get("Current")]
        if current:
            print(f"    okres bieżący: Id={current[0]['Id']} nr {current[0].get('Number')}")


KINDS = ("schedule", "exams", "homework", "grades", "notes", "lessons", "messages", "addressbook",
         "lucky", "vacations")


def zakres(args: argparse.Namespace) -> tuple[date, date]:
    """Dni z --from/--to, a gdy ich nie ma — z --back/--ahead liczonych od dziś."""
    today = date.today()
    d_from = date.fromisoformat(args.d_from) if getattr(args, "d_from", None) else today - timedelta(days=args.back)
    d_to = date.fromisoformat(args.d_to) if getattr(args, "d_to", None) else today + timedelta(days=args.ahead)
    if d_to < d_from:
        raise SystemExit("--to jest wcześniejsze niż --from")
    return d_from, d_to


async def fetch_kind(api: VulcanApi, acc: dict, kind: str, d_from: date, d_to: date) -> Any:
    today = date.today()
    rest = acc["Unit"]["RestURL"]
    pid = acc["Pupil"]["Id"]
    box = (acc.get("MessageBox") or {}).get("GlobalKey")
    if kind == "schedule":
        return await api.schedule(rest, pid, d_from, d_to)
    if kind == "exams":
        return await api.exams(rest, pid, d_from, d_to)
    if kind == "homework":
        return await api.homework(rest, pid, d_from, d_to)
    if kind == "lessons":
        return await api.lessons(rest, pid, d_from, d_to)
    if kind == "vacations":
        return await api.vacations(rest, pid, d_from, d_to)
    if kind == "notes":
        return await api.notes(rest, pid)
    if kind == "grades":
        period = next(p for p in acc["Periods"] if p.get("Current"))
        return await api.grades(rest, pid, acc["Unit"]["Id"], period["Id"])
    if kind == "lucky":
        constituent = (acc.get("ConstituentUnit") or {}).get("Id")
        if constituent is None:
            raise SystemExit("konto nie ma ConstituentUnit — brak numerka")
        return await api.lucky_number(rest, pid, constituent, today)
    if kind in ("messages", "addressbook"):
        if not box:
            raise SystemExit("konto nie ma skrzynki wiadomości")
        return await (api.messages_received if kind == "messages" else api.addressbook)(rest, pid, box)
    raise SystemExit(f"nieznany rodzaj: {kind} (znane: {', '.join(KINDS)})")


async def cmd_fetch(args: argparse.Namespace) -> None:
    async with VulcanApi(Credential.load(args.credential)) as api:
        acc = pick(await api.accounts(), args.pupil)
        out = await fetch_kind(api, acc, args.kind, *zakres(args))
    dump(out)


async def cmd_schema(args: argparse.Namespace) -> None:
    """Kształt odpowiedzi — pola, typy, maski. Żadnych treści (chyba że --values)."""
    async with VulcanApi(Credential.load(args.credential)) as api:
        acc = pick(await api.accounts(), args.pupil)
        out = await fetch_kind(api, acc, args.kind, *zakres(args))
    if args.values:
        counts = schema.values_at(out, args.values)
        if not counts:
            raise SystemExit(f"ścieżka {args.values} nic nie zwróciła — sprawdź ją w `vulcan schema {args.kind}`")
        print(f"{args.kind} → {args.values}")
        for value, n in counts.most_common():
            print(f"  {n:>5} × {value}")
        return
    print(schema.render(args.kind, out))


PARSERY = {
    "lessons": "parse_attendance",
    "schedule": "parse_lesson",
    "exams": "parse_exam",
    "homework": "parse_homework",
    "grades": "parse_grade",
    "notes": "parse_note",
    "messages": "parse_message",
}


def wczytaj_model():
    """Warstwa normalizacji integracji, wczytana z pliku obok klienta.

    Nie `from .. import model`: pakiet instaluje się jako samodzielny `vulcan_client`,
    a `custom_components.vulcan_dom.__init__` ciągnie Home Assistanta. Ładujemy sam
    plik (model nie importuje HA) i rejestrujemy go w `sys.modules`, bo dataclasses
    sięgają po `__module__` przy budowie klas.
    """
    import importlib.util  # noqa: PLC0415

    sciezka = Path(__file__).resolve().parent.parent / "model.py"
    if not sciezka.exists():
        raise SystemExit(f"nie widzę {sciezka} — `parse` działa w klonie repozytorium, nie po samej instalacji klienta")
    spec = importlib.util.spec_from_file_location("vulcan_model", sciezka)
    model = importlib.util.module_from_spec(spec)
    sys.modules["vulcan_model"] = model
    spec.loader.exec_module(model)
    return model


async def cmd_parse(args: argparse.Namespace) -> None:
    """Ile z tego, co zwraca serwer, parser w ogóle rozpoznaje.

    Pętla „popraw parser → sprawdź" bez restartu Home Assistanta. Wypisujemy liczby
    i nazwy pól, nigdy treści: dokładnie to, czego brakowało, gdy parse_attendance
    po cichu odrzucał wszystkie lekcje przez nieznaną nazwę pola z datą.
    """
    if args.kind not in PARSERY:
        raise SystemExit(f"dla '{args.kind}' nie ma parsera (są: {', '.join(sorted(PARSERY))})")
    model = wczytaj_model()
    parser = getattr(model, PARSERY[args.kind])
    async with VulcanApi(Credential.load(args.credential)) as api:
        acc = pick(await api.accounts(), args.pupil)
        surowe = await fetch_kind(api, acc, args.kind, *zakres(args))

    items = surowe if isinstance(surowe, list) else [surowe]
    wyniki, bledy = [], Counter()
    for rec in items:
        try:
            wyniki.append(parser(rec))
        except Exception as err:  # noqa: BLE001 — chcemy policzyć, nie wywrócić się
            bledy[type(err).__name__] += 1
            wyniki.append(None)
    rozpoznane = [w for w in wyniki if w is not None]

    print(f"{args.kind}: rekordów {len(items)}, rozpoznanych {len(rozpoznane)}, odrzuconych {len(items) - len(rozpoznane)}")
    for nazwa, ile in bledy.most_common():
        print(f"  wyjątek {nazwa}: {ile}×")
    if len(rozpoznane) < len(items):
        odrzucone = [r for r, w in zip(items, wyniki, strict=True) if w is None and isinstance(r, dict)]
        pola = sorted({k for r in odrzucone for k in r})
        print("  pola odrzuconych rekordów: " + (", ".join(pola) or "brak"))
    if args.pola and rozpoznane:
        print("  pola rozpoznanych obiektów:")
        for nazwa in sorted(vars(rozpoznane[0])):
            ile = sum(1 for w in rozpoznane if getattr(w, nazwa, None) not in (None, "", False))
            print(f"    {nazwa:<22} niepustych {ile}/{len(rozpoznane)}")


async def cmd_fixture(args: argparse.Namespace) -> None:
    """Zamaskowane rekordy do testów: kształt zachowany, treść nie.

    Teksty idą przez maskę ze `schema` (cyfra→N, wielka→A, mała→a), więc daty i
    identyfikatory zachowują format, a nazwiska, oceny i uwagi nie wychodzą z domu.
    Daty zostawiamy czytelne tylko z --daty, gdy test ma zależeć od konkretnego dnia.
    """
    async with VulcanApi(Credential.load(args.credential)) as api:
        acc = pick(await api.accounts(), args.pupil)
        surowe = await fetch_kind(api, acc, args.kind, *zakres(args))
    items = surowe if isinstance(surowe, list) else [surowe]
    dump([maskuj(r, args.daty) for r in items[: args.limit]])


DATA_MASKA = "NNNN-NN-NN"


def maskuj(value: Any, daty: bool) -> Any:
    """Rekurencyjnie maskuje teksty; liczby i wartości logiczne zostawia bez zmian."""
    if isinstance(value, dict):
        return {k: maskuj(v, daty) for k, v in value.items()}
    if isinstance(value, list):
        return [maskuj(v, daty) for v in value]
    if isinstance(value, str):
        if daty and schema.mask(value[:10]) == DATA_MASKA:
            return value
        return schema.mask(value)
    return value


async def cmd_send_message(args: argparse.Namespace) -> None:
    async with VulcanApi(Credential.load(args.credential)) as api:
        acc = pick(await api.accounts(), args.pupil)
        rest, pid, box = acc["Unit"]["RestURL"], acc["Pupil"]["Id"], acc["MessageBox"]
        book = await api.addressbook(rest, pid, box["GlobalKey"])
        receivers = [r for r in book if args.to.lower() in r.get("Name", "").lower()]
        if len(receivers) != 1:
            names = [r.get("Name") for r in receivers] or "(brak)"
            raise SystemExit(f"adresat musi być jednoznaczny, pasują: {names}")
        content = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else args.body
        payload = api.message_payload(box["GlobalKey"], box["Name"], receivers, args.subject, content)
        print(f"Do: {receivers[0]['Name']}\nTemat: {args.subject}\n---\n{content}\n---")
        if not args.send:
            print("PODGLĄD — nic nie wysłano. Dodaj --send, aby wysłać.")
            return
        await api.send_message(rest, pid, payload)
        print("wysłano")


async def cmd_justify(args: argparse.Namespace) -> None:
    day = date.fromisoformat(args.day)
    async with VulcanApi(Credential.load(args.credential)) as api:
        acc = pick(await api.accounts(), args.pupil)
        rest, pid, login = acc["Unit"]["RestURL"], acc["Pupil"]["Id"], acc["Pupil"]["LoginId"]
        lessons = await api.lessons(rest, pid, day, day)
        def wanted(lesson: dict) -> bool:
            if not lesson.get("LessonClassId"):
                return False
            if args.lesson:
                return (lesson.get("TimeSlot") or {}).get("Position") in args.lesson
            pres = lesson.get("PresenceType") or {}
            return bool(pres.get("Absence")) and not pres.get("AbsenceJustified")

        targets = [l for l in lessons if wanted(l)]
        if not targets:
            raise SystemExit("brak lekcji do usprawiedliwienia w tym dniu (sprawdź `vulcan fetch lessons`)")
        for l in targets:
            subj = (l.get("Subject") or {}).get("Name")
            pres = (l.get("PresenceType") or {}).get("Name")
            print(f"  lekcja {l.get('TimeSlot', {}).get('Position')}: {subj} — {pres} (LessonClassId={l['LessonClassId']})")
        print(f"Powód: {args.reason}")
        if not args.send:
            print("PODGLĄD — nic nie wysłano. Dodaj --send, aby wysłać.")
            return
        for l in targets:
            await api.justify_lesson(rest, pid, api.justification_payload(pid, login, l["LessonClassId"], args.reason))
        print(f"wysłano usprawiedliwień: {len(targets)}")


async def cmd_unregister(args: argparse.Namespace) -> None:
    if not args.yes:
        raise SystemExit("dodaj --yes, aby wyrejestrować urządzenie")
    async with VulcanApi(Credential.load(args.credential)) as api:
        await api.unregister()
    print("wyrejestrowano; plik klucza możesz usunąć")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vulcan", description="Klient eduVULCAN (API mobilne)")
    p.add_argument("--credential", type=Path, default=DEFAULT_CRED)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register", help="rejestracja urządzenia z JSON /api/ap")
    r.add_argument("file", nargs="?", default="-")
    r.add_argument("--device-model", default="SM-A525F")
    r.add_argument("--force", action="store_true")
    r.set_defaults(func=cmd_register)

    sub.add_parser("accounts").set_defaults(func=cmd_accounts)

    f = sub.add_parser("fetch")
    f.add_argument("kind", choices=KINDS)
    f.add_argument("--pupil", type=int)
    f.add_argument("--back", type=int, default=7, help="dni wstecz")
    f.add_argument("--ahead", type=int, default=14, help="dni naprzód")
    f.add_argument("--from", dest="d_from", metavar="RRRR-MM-DD")
    f.add_argument("--to", dest="d_to", metavar="RRRR-MM-DD")
    f.set_defaults(func=cmd_fetch)

    s = sub.add_parser("schema", help="pola i typy odpowiedzi, bez treści")
    s.add_argument("kind", choices=KINDS)
    s.add_argument("--pupil", type=int)
    s.add_argument("--back", type=int, default=7, help="dni wstecz")
    s.add_argument("--ahead", type=int, default=14, help="dni naprzód")
    s.add_argument("--from", dest="d_from", metavar="RRRR-MM-DD")
    s.add_argument("--to", dest="d_to", metavar="RRRR-MM-DD")
    s.add_argument("--values", metavar="ŚCIEŻKA",
                   help="rozkład wartości jednej ścieżki, np. '[].PresenceType.Name' (pokazuje treść!)")
    s.set_defaults(func=cmd_schema)

    pa = sub.add_parser("parse", help="ile rekordów rozpoznaje parser integracji")
    pa.add_argument("kind", choices=sorted(PARSERY))
    pa.add_argument("--pupil", type=int)
    pa.add_argument("--back", type=int, default=7, help="dni wstecz")
    pa.add_argument("--ahead", type=int, default=14, help="dni naprzód")
    pa.add_argument("--from", dest="d_from", metavar="RRRR-MM-DD")
    pa.add_argument("--to", dest="d_to", metavar="RRRR-MM-DD")
    pa.add_argument("--pola", action="store_true", help="ile pól wyniku jest wypełnionych")
    pa.set_defaults(func=cmd_parse)

    fx = sub.add_parser("fixture", help="zamaskowane rekordy do testów")
    fx.add_argument("kind", choices=KINDS)
    fx.add_argument("--pupil", type=int)
    fx.add_argument("--back", type=int, default=7, help="dni wstecz")
    fx.add_argument("--ahead", type=int, default=14, help="dni naprzód")
    fx.add_argument("--from", dest="d_from", metavar="RRRR-MM-DD")
    fx.add_argument("--to", dest="d_to", metavar="RRRR-MM-DD")
    fx.add_argument("--limit", type=int, default=20)
    fx.add_argument("--daty", action="store_true", help="zostaw prawdziwe daty (same daty, nic więcej)")
    fx.set_defaults(func=cmd_fixture)

    m = sub.add_parser("send-message")
    m.add_argument("--pupil", type=int)
    m.add_argument("--to", required=True, help="fragment nazwy adresata z książki adresowej")
    m.add_argument("--subject", required=True)
    g = m.add_mutually_exclusive_group(required=True)
    g.add_argument("--body")
    g.add_argument("--body-file")
    m.add_argument("--send", action="store_true")
    m.set_defaults(func=cmd_send_message)

    j = sub.add_parser("justify")
    j.add_argument("--pupil", type=int)
    j.add_argument("--day", required=True, help="RRRR-MM-DD")
    j.add_argument("--lesson", type=int, action="append", help="numer lekcji (można wiele); brak = cały dzień")
    j.add_argument("--reason", required=True)
    j.add_argument("--send", action="store_true")
    j.set_defaults(func=cmd_justify)

    u = sub.add_parser("unregister")
    u.add_argument("--yes", action="store_true")
    u.set_defaults(func=cmd_unregister)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        asyncio.run(args.func(args))
    except VulcanError as err:
        raise SystemExit(f"błąd: {err}") from None


if __name__ == "__main__":
    main()
