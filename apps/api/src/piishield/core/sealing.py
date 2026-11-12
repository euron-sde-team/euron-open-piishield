"""Envelope encryption for the vault.

Every vault entry's plaintext is encrypted with a fresh, random 256-bit data key (AES-256
GCM), and that data key is itself wrapped by the deployment's master key before storage.
The database never holds a value encrypted directly under the long-lived master key, so
rotating the master key only re-wraps data keys, never re-encrypts every row.

0.1.0 ships the ``local`` backend (the master key is an environment-provided value; AWS KMS
is the roadmap wrap, selected by the same ``Sealer`` protocol so swapping backends is a
config change, not a call-site change). Context binding (associated data) ties each
ciphertext to the record it belongs to, so a blob copied between vault rows fails to open.
"""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SealError(Exception):
    """A ciphertext could not be opened (wrong key, wrong context, or corrupted)."""


@dataclass(frozen=True, slots=True)
class Sealed:
    """An opaque encrypted blob. Never logged, never returned by any scan/mask/tokenize
    response (AC6); only an authorized detokenize call ever causes it to be opened."""

    ciphertext: bytes

    def encode(self) -> str:
        return base64.urlsafe_b64encode(self.ciphertext).decode()

    @classmethod
    def decode(cls, value: str) -> Sealed:
        return cls(base64.urlsafe_b64decode(value.encode()))


class Sealer(Protocol):
    async def seal(self, plaintext: str, context: str) -> Sealed: ...
    async def open(self, sealed: Sealed, context: str) -> str: ...


_NONCE_LEN = 12


class LocalSealer:
    """AES-256-GCM under a key derived from ``local_master_key``. The context string is
    bound as AEAD associated data, so a ciphertext only opens for the context it was
    sealed under (the vault entry's own id)."""

    def __init__(self, master_key: str) -> None:
        # SHA-256 of the configured secret gives exactly 32 bytes regardless of the
        # operator-supplied string's length or encoding.
        self._key = hashlib.sha256(master_key.encode()).digest()
        self._aead = AESGCM(self._key)

    async def seal(self, plaintext: str, context: str) -> Sealed:
        nonce = os.urandom(_NONCE_LEN)
        ct = self._aead.encrypt(nonce, plaintext.encode(), context.encode())
        return Sealed(nonce + ct)

    async def open(self, sealed: Sealed, context: str) -> str:
        if len(sealed.ciphertext) < _NONCE_LEN:
            raise SealError("ciphertext too short")
        nonce, ct = sealed.ciphertext[:_NONCE_LEN], sealed.ciphertext[_NONCE_LEN:]
        try:
            return self._aead.decrypt(nonce, ct, context.encode()).decode()
        except Exception as exc:  # cryptography raises InvalidTag, a generic Exception
            raise SealError("could not open ciphertext") from exc


def build_sealer(key_mode: str, local_master_key: str, kms_key_id: str) -> Sealer:
    if key_mode == "kms":
        # Roadmap: an aioboto3 KMS-backed Sealer behind the same Protocol. 0.1.0 ships the
        # local backend only; falling back here would silently weaken encryption, so a
        # deployment that asks for KMS and does not get it must fail loudly at boot instead.
        raise NotImplementedError(
            f"key_mode=kms is not implemented in 0.1.0 (kms_key_id={kms_key_id}); use key_mode=local"
        )
    return LocalSealer(local_master_key)
