"""CLI do testów klienta poza Home Assistantem.

  vulcan register [PLIK|-]     rejestracja urządzenia z JSON-a z eduvulcan.pl/api/ap
  vulcan accounts              uczniowie, szkoła, uprawnienia (Capabilities)
  vulcan fetch RODZAJ          surowy JSON: schedule|exams|homework|grades|notes|lessons|
                               messages|addressbook|lucky|vacations
  vulcan send-message ...      podgląd treści; wysyłka dopiero z --send
  vulcan justify ...           podgląd; wysyłka dopiero z --send
  vulcan unregister            wyrejestrowanie urządzenia (z --yes)

Plik z kluczem: $VULCAN_CREDENTIAL albo ~/.config/vulcan/credential.json (0600).
Nic z tego pliku nie trafia na wyjście.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

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


async def cmd_fetch(args: argparse.Namespace) -> None:
    today = date.today()
    d_from = today - timedelta(days=args.back)
    d_to = today + timedelta(days=args.ahead)
    async with VulcanApi(Credential.load(args.credential)) as api:
        acc = pick(await api.accounts(), args.pupil)
        rest = acc["Unit"]["RestURL"]
        pid = acc["Pupil"]["Id"]
        box = (acc.get("MessageBox") or {}).get("GlobalKey")
        kind = args.kind
        if kind == "schedule":
            out = await api.schedule(rest, pid, d_from, d_to)
        elif kind == "exams":
            out = await api.exams(rest, pid, d_from, d_to)
        elif kind == "homework":
            out = await api.homework(rest, pid, d_from, d_to)
        elif kind == "lessons":
            out = await api.lessons(rest, pid, d_from, d_to)
        elif kind == "vacations":
            out = await api.vacations(rest, pid, d_from, d_to)
        elif kind == "notes":
            out = await api.notes(rest, pid)
        elif kind == "grades":
            period = next(p for p in acc["Periods"] if p.get("Current"))
            out = await api.grades(rest, pid, acc["Unit"]["Id"], period["Id"])
        elif kind == "lucky":
            out = await api.lucky_number(rest, pid, acc["ConstituentUnit"]["Id"], today)
        elif kind in ("messages", "addressbook"):
            if not box:
                raise SystemExit("konto nie ma skrzynki wiadomości")
            out = await (api.messages_received if kind == "messages" else api.addressbook)(rest, pid, box)
        else:
            raise SystemExit(f"nieznany rodzaj: {kind}")
    dump(out)


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
    f.add_argument("kind")
    f.add_argument("--pupil", type=int)
    f.add_argument("--back", type=int, default=7, help="dni wstecz")
    f.add_argument("--ahead", type=int, default=14, help="dni naprzód")
    f.set_defaults(func=cmd_fetch)

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
