"""Testy na danych syntetycznych — bez sieci i bez prawdziwych kont."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import stat
from base64 import b64decode

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from vulcan_client import ApiError, AuthError, Credential, TransportError, VulcanApi
from vulcan_client.cli import parse_ap
from vulcan_client.http import canonical_url

REST = "https://lekcjaplus.vulcan.net.pl/testowo/api"


def envelope(payload, code=0, message="OK"):
    return {
        "EnvelopeType": "x",
        "Envelope": payload,
        "Status": {"Code": code, "Message": message},
        "RequestId": "r",
        "Timestamp": 0,
        "TimestampFormatted": "",
    }


class FakeResponse:
    def __init__(self, status, text):
        self.status, self._text = status, text

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Zamiast sieci: zapisuje żądania, zwraca kolejne przygotowane odpowiedzi."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, params=None, data=None, headers=None):
        self.calls.append({"method": method, "url": url, "params": params, "data": data, "headers": headers})
        status, body = self.responses.pop(0)
        return FakeResponse(status, body if isinstance(body, str) else json.dumps(body))

    async def close(self):
        pass


def fake_jwt(tenant: str) -> str:
    def b64(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")

    return f"{b64({'alg': 'none'})}.{b64({'tenant': tenant, 'name': 'Jan Testowy', 'uid': 'u'})}.sig"


@pytest.fixture
def cred():
    c = Credential.create()
    c.rest_url = REST
    return c


def test_signature_verifies_with_public_key(cred):
    body = '{"a":1}'
    headers = cred.sign({"vCanonicalUrl": "api%2fmobile%2fx", "vDate": "Mon, 12 Oct 2026 10:00:00 GMT"}, body)
    assert headers["Digest"] == "SHA-256=" + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
    m = re.search(r'keyId="([^"]+)",headers="([^"]+)",algorithm="sha256withrsa",signature=Base64\(SHA256withRSA\((.+)\)\)', headers["Signature"])
    assert m and m[1] == cred.fingerprint and m[2] == "vCanonicalUrl Digest vDate"
    pub = serialization.load_der_public_key(b64decode(cred.certificate))
    signed = "api%2fmobile%2fx" + headers["Digest"].removeprefix("SHA-256=") + "Mon, 12 Oct 2026 10:00:00 GMT"
    pub.verify(b64decode(m[3]), signed.encode(), padding.PKCS1v15(), hashes.SHA256())


def test_signature_without_body(cred):
    headers = cred.sign({"vCanonicalUrl": "x", "vDate": "d"}, None)
    assert "Digest" not in headers and 'headers="vCanonicalUrl vDate"' in headers["Signature"]


def test_canonical_url():
    assert canonical_url(f"{REST}/mobile/exam/byPupil") == "api%2fmobile%2fexam%2fbypupil"


def test_credential_saved_private(tmp_path, cred):
    path = tmp_path / "sub" / "credential.json"
    cred.save(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert Credential.load(path) == cred


def test_parse_ap_groups_tokens_and_validates():
    ap = {"Success": True, "IsConsentAccepted": True, "Tokens": [fake_jwt("testowo"), fake_jwt("testowo")]}
    assert list(parse_ap(json.dumps(ap))) == ["testowo"]
    with pytest.raises(SystemExit):
        parse_ap(json.dumps({**ap, "IsConsentAccepted": False}))
    with pytest.raises(SystemExit):
        parse_ap(json.dumps({**ap, "Tokens": []}))


async def test_get_sends_signed_request_and_unwraps(cred):
    from datetime import date

    session = FakeSession((200, envelope([{"Id": 1}])))
    api = VulcanApi(cred, session)
    out = await api.exams(REST, 42, date(2026, 10, 1), date(2026, 10, 31))
    assert out == [{"Id": 1}]
    call = session.calls[0]
    assert call["url"] == f"{REST}/mobile/exam/byPupil"
    assert call["params"]["pupilId"] == "42" and call["params"]["dateFrom"] == "2026-10-01"
    assert call["headers"]["vHint"] == "42" and "Signature" in call["headers"]
    assert call["data"] is None


async def test_auth_and_api_errors(cred):
    api = VulcanApi(cred, FakeSession((200, envelope(None, 154, "cert"))))
    with pytest.raises(AuthError):
        await api.accounts()
    api = VulcanApi(cred, FakeSession((200, envelope(None, 206, "bad"))))
    with pytest.raises(ApiError):
        await api.notes(REST, 1)


async def test_html_and_http_errors_are_transport_errors(cred):
    api = VulcanApi(cred, FakeSession((200, "<!DOCTYPE html><html></html>"), (502, "bad gateway")))
    with pytest.raises(TransportError):
        await api.accounts()
    with pytest.raises(TransportError):
        await api.accounts()


async def test_send_message_body(cred):
    payload = VulcanApi.message_payload(
        "box-1", "Rodzic Testowy", [{"GlobalKey": "t-1", "Name": "Nauczyciel"}], "Temat", "Treść"
    )
    assert payload["Sender"] == {"GlobalKey": "box-1", "Name": "Rodzic Testowy"}
    session = FakeSession((200, envelope(None)))
    await VulcanApi(cred, session).send_message(REST, 7, payload)
    call = session.calls[0]
    assert call["method"] == "POST" and call["url"] == f"{REST}/mobile/messages"
    sent = json.loads(call["data"])
    assert sent["Envelope"] == payload and sent["AppName"]
    assert call["headers"]["Digest"].startswith("SHA-256=")


def test_justification_payload():
    assert VulcanApi.justification_payload(1, 2, 3, "choroba") == {
        "Reason": "choroba",
        "LessonClassId": 3,
        "PupilId": 1,
        "LoginId": 2,
    }
