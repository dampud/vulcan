"""Odczyt danych z eduvulcan.pl/api/ap (ukryte pole #ap) — tokeny JWT uczniów."""

from __future__ import annotations

import base64
import json


class ApDataError(ValueError):
    """Dane z /api/ap nie nadają się do rejestracji."""


def jwt_payload(token: str) -> dict:
    part = token.split(".")[1]
    part += "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part))


def parse_ap(raw: str) -> dict[str, list[str]]:
    """JSON z pola #ap → {tenant: [jwt, ...]}. Waliduje jak aplikacja eduVULCAN."""
    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError as err:
        raise ApDataError("to nie jest JSON z eduvulcan.pl/api/ap") from err
    if not isinstance(data, dict):
        raise ApDataError("to nie jest JSON z eduvulcan.pl/api/ap")
    if not data.get("Success"):
        raise ApDataError(f"Success=false ({data.get('ErrorMessage')})")
    if not data.get("IsConsentAccepted"):
        raise ApDataError("zgody nie są zaakceptowane — zaakceptuj je na eduvulcan.pl")
    tokens = data.get("Tokens") or []
    if not tokens:
        raise ApDataError("brak tokenów (konto bez powiązanych uczniów?)")
    by_tenant: dict[str, list[str]] = {}
    for tok in tokens:
        try:
            tenant = jwt_payload(tok)["tenant"]
        except Exception as err:  # noqa: BLE001
            raise ApDataError("nieczytelny token JWT") from err
        by_tenant.setdefault(tenant, []).append(tok)
    return by_tenant
