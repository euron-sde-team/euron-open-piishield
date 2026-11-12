"""Unit tests for the vault's envelope encryption (AES-256-GCM, context-bound)."""

from __future__ import annotations

import pytest

from piishield.core.sealing import LocalSealer, Sealed, SealError


@pytest.fixture
def sealer() -> LocalSealer:
    return LocalSealer("test-local-master-key-not-for-production-xx")


@pytest.mark.asyncio
async def test_seal_then_open_round_trips(sealer: LocalSealer) -> None:
    sealed = await sealer.seal("ananya.gupta@example.com", "vault:entry-1")
    opened = await sealer.open(sealed, "vault:entry-1")
    assert opened == "ananya.gupta@example.com"


@pytest.mark.asyncio
async def test_ciphertext_never_contains_plaintext(sealer: LocalSealer) -> None:
    sealed = await sealer.seal("4539148803436467", "vault:entry-2")
    assert b"4539148803436467" not in sealed.ciphertext


@pytest.mark.asyncio
async def test_open_with_wrong_context_fails(sealer: LocalSealer) -> None:
    sealed = await sealer.seal("secret-value", "vault:entry-3")
    with pytest.raises(SealError):
        await sealer.open(sealed, "vault:entry-OTHER")


@pytest.mark.asyncio
async def test_open_with_wrong_key_fails() -> None:
    sealer_a = LocalSealer("key-a-not-for-production-use-at-all-xxxxx")
    sealer_b = LocalSealer("key-b-not-for-production-use-at-all-xxxxx")
    sealed = await sealer_a.seal("secret-value", "vault:entry-4")
    with pytest.raises(SealError):
        await sealer_b.open(sealed, "vault:entry-4")


def test_sealed_encode_decode_round_trip() -> None:
    sealed = Sealed(b"\x00\x01\x02some-ciphertext-bytes")
    decoded = Sealed.decode(sealed.encode())
    assert decoded.ciphertext == sealed.ciphertext
