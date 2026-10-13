#!/usr/bin/env python3
"""Pilnuje, żeby wersja była w repo jedna.

`manifest.json` czyta HACS i Home Assistant, `pyproject.toml` — instalacja klienta.
Rozjazd między nimi jest cichy: HACS pokazuje jedno, pip instaluje drugie. Przy
budowie z tagu sprawdzamy dodatkowo, czy tag zgadza się z wersją w plikach.

Użycie:
    python skrypty/sprawdz_wersje.py            # spójność plików
    python skrypty/sprawdz_wersje.py v0.4.0     # dodatkowo zgodność z tagiem
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

KORZEN = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = KORZEN / "custom_components" / "vulcan_dom" / "manifest.json"
PYPROJECT = KORZEN / "pyproject.toml"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")).get("version", "")
    znaleziona = re.search(r'^version = "([^"]+)"', PYPROJECT.read_text(encoding="utf-8"), re.M)
    pyproject = znaleziona.group(1) if znaleziona else ""

    bledy: list[str] = []
    if not SEMVER.match(manifest):
        bledy.append(f"manifest.json: '{manifest}' to nie jest wersja w formacie X.Y.Z")
    if manifest != pyproject:
        bledy.append(f"rozjazd wersji: manifest.json={manifest}, pyproject.toml={pyproject}")

    if len(sys.argv) > 1:
        tag = sys.argv[1].removeprefix("v")
        if tag != manifest:
            bledy.append(f"tag v{tag} nie zgadza się z wersją w plikach ({manifest})")

    for blad in bledy:
        print(f"BŁĄD: {blad}", file=sys.stderr)
    if bledy:
        return 1
    print(f"wersja spójna: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
