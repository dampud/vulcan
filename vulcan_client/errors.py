"""Wyjątki klienta. Kody statusu koperty wg iris (bbrjpl1310b/iris, AGPL-3.0)."""

from __future__ import annotations


class VulcanError(Exception):
    """Błąd bazowy."""


class TransportError(VulcanError):
    """Sieć, timeout, status HTTP != 200 albo odpowiedź HTML zamiast JSON."""


class ApiError(VulcanError):
    """Serwer odpowiedział kopertą ze statusem != 0."""

    def __init__(self, code: int, message: str | None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class AuthError(ApiError):
    """Problem z certyfikatem/podpisem/tokenem — wymaga ponownej rejestracji."""


# Kody, po których nie ma sensu ponawiać bez działania człowieka.
AUTH_CODES = {100, 102, 103, 154, 201, 202, 203, 204}

KNOWN_CODES = {
    -1: "błąd wewnętrzny serwera",
    100: "nieprawidłowy podpis",
    101: "nieprawidłowy model treści",
    102: "brak nagłówka",
    103: "nieprawidłowy nagłówek",
    104: "brak symbolu jednostki",
    154: "nie znaleziono certyfikatu (urządzenie wyrejestrowane?)",
    200: "nie znaleziono obiektu",
    201: "token już użyty",
    202: "nieprawidłowy token",
    203: "nieprawidłowy PIN",
    204: "token wygasł",
    206: "nieprawidłowa wartość parametru",
    214: "naruszenie ograniczeń",
}


def raise_for_status(code: int, message: str | None) -> None:
    if code == 0:
        return
    text = message or KNOWN_CODES.get(code)
    if code in AUTH_CODES:
        raise AuthError(code, text)
    raise ApiError(code, text)
