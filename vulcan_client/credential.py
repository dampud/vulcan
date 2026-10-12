"""Certyfikat urządzenia i podpisywanie żądań (schemat jak w aplikacji eduVULCAN).

Podpis: RSA PKCS#1 v1.5 + SHA-256 nad połączonymi wartościami nagłówków
vCanonicalUrl [+ Digest] + vDate. Port z iris (bbrjpl1310b/iris, AGPL-3.0).
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from base64 import b64decode, b64encode
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def _pem_body(pem: bytes) -> str:
    return pem.decode("ascii").replace("\n", "").split("-----")[2]


@dataclass
class Credential:
    certificate: str  # klucz publiczny (DER, base64)
    private_key: str  # klucz prywatny (DER PKCS#1, base64) — SEKRET
    fingerprint: str
    device_id: str
    device_os: Literal["Android", "iOS"] = "Android"
    device_model: str = "SM-A525F"
    type: str = "RSA_PEM"
    rest_url: str | None = None  # https://lekcjaplus.vulcan.net.pl/<tenant>/api po rejestracji
    notification_token: str = ""
    extra: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls, device_os: Literal["Android", "iOS"] = "Android", device_model: str = "SM-A525F"
    ) -> "Credential":
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
        public_pem = key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return cls(
            certificate=_pem_body(public_pem),
            private_key=_pem_body(private_pem),
            fingerprint=hashlib.md5(public_pem).hexdigest(),
            device_id=str(uuid.uuid4()),
            device_os=device_os,
            device_model=device_model,
        )

    # --- podpis -----------------------------------------------------------

    def sign(self, headers: dict[str, str], body: str | None) -> dict[str, str]:
        key = serialization.load_der_private_key(b64decode(self.private_key), password=None)
        names = ["vCanonicalUrl", "vDate"]
        if body is not None:
            digest = b64encode(hashlib.sha256(body.encode()).digest()).decode()
            headers["Digest"] = digest
            names = ["vCanonicalUrl", "Digest", "vDate"]
        payload = "".join(headers[n] for n in names).encode()
        signature = b64encode(key.sign(payload, padding.PKCS1v15(), hashes.SHA256())).decode()
        headers["Signature"] = (
            f'keyId="{self.fingerprint}",headers="{" ".join(names)}",'
            f'algorithm="sha256withrsa",signature=Base64(SHA256withRSA({signature}))'
        )
        if body is not None:
            headers["Digest"] = f"SHA-256={headers['Digest']}"
        return headers

    # --- zapis/odczyt -----------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Credential":
        return cls(**data)

    def save(self, path: str | os.PathLike) -> None:
        """Zapis z prawami 0600 — plik zawiera klucz prywatny."""
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    @classmethod
    def load(cls, path: str | os.PathLike) -> "Credential":
        with Path(path).expanduser().open(encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))
