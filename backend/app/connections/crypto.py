"""Encrypts data-connection credentials at rest.

Fernet needs a 32-byte urlsafe-base64 key; connection_secret_key is an
arbitrary string, so it's stretched into a valid key deterministically (same
input -> same key, always) rather than generated randomly at import time.
A random key would make every stored connection's credentials permanently
undecryptable the moment the process restarts.
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().connection_secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_config(config: dict[str, Any]) -> str:
    payload = json.dumps(config).encode("utf-8")
    return _fernet().encrypt(payload).decode("utf-8")


def decrypt_config(token: str) -> dict[str, Any]:
    payload = _fernet().decrypt(token.encode("utf-8"))
    return json.loads(payload)
