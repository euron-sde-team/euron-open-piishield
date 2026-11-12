"""Smoke tests against a real, running PIIShield API. See conftest.py for the skip rule."""

from __future__ import annotations

import pytest

from euron_piishield import PIIShield, VaultPermissionError


@pytest.mark.integration
def test_scan_finds_pii(shield: PIIShield) -> None:
    result = shield.scan("Email: rahul@example.com")
    assert any(f.recognizer == "email" and f.category == "contact" for f in result.findings)


@pytest.mark.integration
def test_mask_full_mask_replaces_value(shield: PIIShield) -> None:
    result = shield.mask("Email: rahul@example.com", method="full_mask")
    assert "rahul@example.com" not in result.protected_text


@pytest.mark.integration
def test_tokenize_scope_consistency(shield: PIIShield) -> None:
    first = shield.tokenize("rahul@example.com", scope_id="it-session")
    second = shield.tokenize("rahul@example.com", scope_id="it-session")
    assert first.protected_text == second.protected_text


@pytest.mark.integration
def test_detokenize_without_vault_access_raises(shield: PIIShield) -> None:
    protected = shield.tokenize("rahul@example.com", scope_id="it-session-2")
    placeholder = next((f.placeholder for f in protected.findings if f.placeholder), None)
    if placeholder is None:
        pytest.skip("server did not return a placeholder to detokenize")
    with pytest.raises(VaultPermissionError):
        shield.detokenize(placeholder, "it-session-2")


@pytest.mark.integration
def test_protect_then_restore_round_trip(shield: PIIShield) -> None:
    # ABCPE1234F is structurally valid (4th letter P = person; see
    # piishield.detectors.checksums.pan_entity_ok); the earlier example here,
    # ABCDE1234F, is not a real PAN shape ("D" is not a valid entity-type letter) and the
    # real checksum-validated recognizer correctly finds nothing for it.
    protected = shield.protect("My PAN is ABCPE1234F. Explain my tax record.")
    assert "ABCPE1234F" not in protected.protected_text
    model_response = protected.protected_text.replace("Explain", "Explained")
    restored = shield.restore(protected.scope_id, model_response)
    assert "ABCPE1234F" in restored.restored_text
