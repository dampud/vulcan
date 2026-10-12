"""Transport: koperta żądania, nagłówki v*, podpis, weryfikacja koperty odpowiedzi."""

from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import quote

import aiohttp

from .credential import Credential
from .errors import TransportError, raise_for_status

# Tożsamość aplikacji eduVULCAN (jak w iris; aktualizować, gdy serwer zacznie odrzucać).
APP_NAME = "DzienniczekPlus 3.0"
APP_VERSION = "25.09.24 (G)"
APP_VERSION_CODE = "802"
USER_AGENT = "Dart/3.8 (dart:io)"
API_VERSION = 1
BASE_URL = "https://lekcjaplus.vulcan.net.pl"
TIMEOUT = aiohttp.ClientTimeout(total=30)


def canonical_url(url: str) -> str:
    match = re.search(r"(api/mobile/.*)", url)
    return quote(match[0] if match else url, safe="").lower()


def serialize_query(query: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in query.items():
        if value is None:
            continue
        if isinstance(value, datetime):
            out[key] = value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, date):
            out[key] = value.strftime("%Y-%m-%d")
        elif isinstance(value, bool):
            out[key] = "true" if value else "false"
        else:
            out[key] = str(value)
    return out


class HttpClient:
    def __init__(self, credential: Credential, session: aiohttp.ClientSession | None = None):
        self.credential = credential
        self._session = session
        self._own_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=TIMEOUT, skip_auto_headers={"Accept", "Content-Length"}
            )
        return self._session

    async def close(self) -> None:
        if self._own_session and self._session is not None:
            await self._session.close()
            self._session = None

    def build_body(self, envelope: Any) -> str:
        now = datetime.now()
        return json.dumps(
            {
                "AppName": APP_NAME,
                "AppVersion": APP_VERSION,
                "NotificationToken": self.credential.notification_token or "",
                "API": API_VERSION,
                "RequestId": str(uuid.uuid4()),
                "Timestamp": int(now.timestamp()),
                "TimestampFormatted": now.strftime("%Y-%m-%d %H:%M:%S"),
                "Envelope": envelope,
            }
        )

    def build_headers(self, url: str, body: str | None, pupil_id: int | None) -> dict[str, str]:
        headers = {
            "Accept-Encoding": "gzip",
            "vOS": self.credential.device_os,
            "vVersionCode": APP_VERSION_CODE,
            "vAPI": str(API_VERSION),
            "vCanonicalUrl": canonical_url(url),
            "vDate": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json; charset=utf-8" if body else "application/json",
        }
        if pupil_id:
            headers["vHint"] = str(pupil_id)
        if body:
            headers["Content-Length"] = str(len(body.encode()))
        return self.credential.sign(headers, body)

    async def request(
        self,
        method: str,
        endpoint: str,
        rest_url: str | None = None,
        *,
        pupil_id: int | None = None,
        query: dict[str, Any] | None = None,
        payload: Any = None,
    ) -> Any:
        base = rest_url or self.credential.rest_url
        if not base:
            raise TransportError("brak rest_url — najpierw rejestracja urządzenia")
        url = f"{base.rstrip('/')}/{endpoint}"
        body = self.build_body(payload) if payload is not None else None
        headers = self.build_headers(url, body, pupil_id)
        session = await self._get_session()
        try:
            async with session.request(
                method,
                url,
                params=serialize_query(query) if query else None,
                data=body.encode() if body else None,
                headers=headers,
            ) as resp:
                text = await resp.text()
                status = resp.status
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TransportError(f"{method} {endpoint}: {err}") from err

        if status != 200:
            raise TransportError(f"{method} {endpoint}: HTTP {status}: {text[:200]}")
        if "<!DOCTYPE" in text[:200] or "<html" in text[:200].lower():
            raise TransportError(f"{method} {endpoint}: odpowiedź HTML zamiast JSON")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as err:
            raise TransportError(f"{method} {endpoint}: niepoprawny JSON") from err
        status_obj = data.get("Status") or {}
        raise_for_status(int(status_obj.get("Code", -1)), status_obj.get("Message"))
        return data.get("Envelope")
