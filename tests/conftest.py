"""Wspólne atrapy: sesja HTTP udająca Hebe (koperta, stronicowanie, lastSyncDate).

Testy integracji jadą po prawdziwym kliencie — podpis, koperta i stronicowanie też są
sprawdzane po drodze. Podmieniona jest wyłącznie warstwa sieci.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vulcan_dom.const import CONF_CREDENTIAL, CONF_TENANT, DOMAIN
from custom_components.vulcan_dom.vulcan_client import Credential, VulcanApi

from . import dane

pytest_plugins = "pytest_homeassistant_custom_component"

FROZEN = f"{dane.DZIS.isoformat()} 06:30:00+02:00"
EPOCH_TEXT = "1970-01-01 01:00:00"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Bez tego HA nie zobaczy katalogu custom_components."""
    yield


@pytest.fixture(autouse=True)
def frozen_time(freezer):
    freezer.move_to(FROZEN)
    return freezer


@pytest.fixture(scope="session")
def credential() -> Credential:
    """Jeden klucz na całą sesję — generowanie RSA jest wolne."""
    cred = Credential.create()
    cred.rest_url = dane.REST
    return cred


def envelope(payload: Any, code: int = 0, message: str = "OK") -> str:
    return json.dumps({
        "EnvelopeType": "x", "Envelope": payload,
        "Status": {"Code": code, "Message": message},
        "RequestId": "r", "Timestamp": 0, "TimestampFormatted": "",
    }, default=str)


class _Response:
    def __init__(self, status: int, text: str) -> None:
        self.status, self._text = status, text

    async def text(self) -> str:
        return self._text

    async def __aenter__(self) -> "_Response":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


class HebeSession:
    """Atrapa aiohttp: trasuje po ścieżce, tnie listy na strony po `lastId`.

    `fail` podmienia odpowiedź dla ścieżki (kod koperty albo status HTTP), `data`
    pozwala podmienić zestaw rekordów w trakcie testu.
    """

    PAGE = 500

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.data: dict[str, Any] = {
            "mobile/register/hebe": [dane.ACCOUNT],
            "mobile/schedule/withchanges/byPupil": list(dane.SCHEDULE),
            "mobile/exam/byPupil": list(dane.EXAMS),
            "mobile/homework/byPupil": list(dane.HOMEWORK),
            "mobile/grade/byPupil": list(dane.GRADES),
            "mobile/note/byPupil": list(dane.NOTES),
            "mobile/lesson/byPupil": list(dane.LESSONS),
            "mobile/messages/received/byBox": list(dane.MESSAGES),
            "mobile/addressbook": list(dane.ADDRESSBOOK),
            "mobile/school/lucky": dict(dane.LUCKY),
            "mobile/register/jwt": None,
            "mobile/messages": None,
            "mobile/presence/justification/lesson": None,
        }
        self.fail: dict[str, tuple[int, int]] = {}  # ścieżka -> (status HTTP, kod koperty)
        self.page_size = self.PAGE

    # --- pomocnicze dla testów -------------------------------------------

    def path_calls(self, path: str) -> list[dict]:
        return [c for c in self.calls if c["path"] == path]

    def bodies(self, path: str) -> list[dict]:
        return [json.loads(c["data"])["Envelope"] for c in self.path_calls(path) if c["data"]]

    # --- atrapa aiohttp ---------------------------------------------------

    def request(self, method, url, params=None, data=None, headers=None):
        path = url.split("/api/", 1)[1]
        body = data.decode() if isinstance(data, bytes) else data
        self.calls.append({"method": method, "path": path, "params": params or {}, "data": body,
                           "headers": headers or {}})
        if path in self.fail:
            status, code = self.fail[path]
            if status != 200:
                return _Response(status, "bad gateway")
            return _Response(200, envelope(None, code, "odmowa"))
        return _Response(200, envelope(self._payload(path, params or {})))

    def _payload(self, path: str, params: dict) -> Any:
        records = self.data.get(path)
        if not isinstance(records, list):
            return records
        if path == "mobile/messages/received/byBox":
            records = self._only_modified_since(records, params.get("lastSyncDate"))
        records = self._only_in_window(records, params.get("dateFrom"), params.get("dateTo"))
        last_id = int(params.get("lastId", -2_147_483_648))
        page = [r for r in records if int(r.get("Id", 0)) > last_id]
        page.sort(key=lambda r: int(r.get("Id", 0)))
        return page[: self.page_size]

    @staticmethod
    def _only_in_window(records: list[dict], od: str | None, do: str | None) -> list[dict]:
        """Serwer honoruje dateFrom/dateTo — atrapa też, inaczej testy okien nic nie znaczą."""
        if not od or not do:
            return records
        out = []
        for rec in records:
            kiedy = rec.get("DateAt") or rec.get("DeadlineAt")
            if kiedy is None or od <= str(kiedy)[:10] <= do:
                out.append(rec)
        return out

    @staticmethod
    def _only_modified_since(records: list[dict], since: str | None) -> list[dict]:
        if not since or since == EPOCH_TEXT:
            return records
        cut = datetime.fromisoformat(since)
        out = []
        for rec in records:
            changed = rec.get("DateModify") or rec.get("SentAt")
            if not changed or datetime.fromisoformat(changed) >= cut:
                out.append(rec)
        return out

    async def close(self) -> None:
        pass


@pytest.fixture
def hebe() -> HebeSession:
    return HebeSession()


@pytest.fixture
def api_patch(hebe, credential):
    """Podmienia konstruktor VulcanApi wszędzie, gdzie integracja go tworzy."""

    def factory(cred, session=None):
        return VulcanApi(cred, hebe)

    with (
        patch("custom_components.vulcan_dom.VulcanApi", side_effect=factory),
        patch("custom_components.vulcan_dom.config_flow.VulcanApi", side_effect=factory),
        patch("custom_components.vulcan_dom.config_flow.Credential.create", return_value=credential),
    ):
        yield hebe


@pytest.fixture
async def entry(hass, credential) -> MockConfigEntry:
    # instancja Damiana chodzi w czasie warszawskim; cisza nocna i "dziś" liczą się
    # po strefie HA, a plan lekcji po Europe/Warsaw — w testach muszą być zgodne
    await hass.config.async_set_time_zone("Europe/Warsaw")
    item = MockConfigEntry(
        domain=DOMAIN,
        title="eduVULCAN – Ala Testowa",
        unique_id=f"{dane.TENANT}-{dane.LOGIN_ID}",
        data={CONF_TENANT: dane.TENANT, CONF_CREDENTIAL: credential.to_dict()},
        options={},
    )
    item.add_to_hass(hass)
    return item


@pytest.fixture
async def setup_entry(hass, entry, api_patch):
    """Wpis skonfigurowany i załadowany; zwraca sesję-atrapę do asercji."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return api_patch
