"""Pure request-building and error-mapping logic: no network."""

from __future__ import annotations

import httpx
import pytest

from euron_piishield import _core
from euron_piishield.errors import (
    APIError,
    PolicyViolationError,
    UnsupportedFileTypeError,
    VaultPermissionError,
)


def test_check_options_rejects_bad_url() -> None:
    with pytest.raises(ValueError, match="http"):
        _core.check_options("not-a-url", "key")


def test_check_options_rejects_empty_key() -> None:
    with pytest.raises(ValueError, match="api_key"):
        _core.check_options("http://x", "")


def test_check_options_strips_trailing_slash() -> None:
    assert _core.check_options("http://x/", "key") == "http://x"


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("report.pdf", "application/pdf"),
        ("data.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("sheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("rows.csv", "text/csv"),
        ("ROWS.CSV", "text/csv"),
    ],
)
def test_guess_content_type(filename: str, expected: str) -> None:
    assert _core.guess_content_type(filename) == expected


def test_guess_content_type_rejects_unknown_extension() -> None:
    with pytest.raises(UnsupportedFileTypeError, match="filename"):
        _core.guess_content_type("photo.png")


def test_protect_text_body_omits_unset_optionals() -> None:
    body = _core.protect_text_body("proj-1", "hi", None, None, None)
    assert body == {"project_id": "proj-1", "text": "hi"}


def test_protect_text_body_includes_set_optionals() -> None:
    body = _core.protect_text_body(
        "proj-1", "hi", {"contact": "partial_mask"}, ["financial"], "scope-1"
    )
    assert body == {
        "project_id": "proj-1",
        "text": "hi",
        "method_overrides": {"contact": "partial_mask"},
        "skip_categories": ["financial"],
        "scope_id": "scope-1",
    }


def test_protect_json_body_wraps_payload() -> None:
    body = _core.protect_json_body("proj-1", {"a": 1}, None, None, None)
    assert body == {"project_id": "proj-1", "payload": {"a": 1}}


def test_error_from_vault_access_required_403_is_vault_permission_error() -> None:
    response = httpx.Response(
        403, json={"error": {"code": "vault_access_required", "message": "no"}}
    )
    error = _core.error_from(response, context="detokenize")
    assert isinstance(error, VaultPermissionError)


def test_error_from_other_403_code_is_plain_api_error() -> None:
    response = httpx.Response(403, json={"error": {"code": "insufficient_role", "message": "no"}})
    error = _core.error_from(response, context="scan")
    assert isinstance(error, APIError)
    assert not isinstance(error, VaultPermissionError)


def test_error_from_required_category_unmasked_422_is_policy_violation() -> None:
    response = httpx.Response(
        422, json={"error": {"code": "required_category_unmasked", "message": "no"}}
    )
    error = _core.error_from(response, context="mask")
    assert isinstance(error, PolicyViolationError)


def test_error_from_other_422_code_is_plain_api_error() -> None:
    response = httpx.Response(422, json={"error": {"code": "validation_error", "message": "no"}})
    error = _core.error_from(response, context="mask")
    assert isinstance(error, APIError)
    assert not isinstance(error, PolicyViolationError)


def test_error_from_unparseable_body_falls_back_to_reason_phrase() -> None:
    response = httpx.Response(500, text="boom")
    error = _core.error_from(response, context="scan")
    assert error.status_code == 500
    assert error.code == "api_error"


def test_env_integration_config_requires_all_three_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PIISHIELD_API_URL", raising=False)
    monkeypatch.delenv("PIISHIELD_API_KEY", raising=False)
    monkeypatch.delenv("PIISHIELD_PROJECT_ID", raising=False)
    assert _core.env_integration_config("PIISHIELD") is None
    monkeypatch.setenv("PIISHIELD_API_URL", "http://x")
    monkeypatch.setenv("PIISHIELD_API_KEY", "key")
    assert _core.env_integration_config("PIISHIELD") is None
    monkeypatch.setenv("PIISHIELD_PROJECT_ID", "proj-1")
    assert _core.env_integration_config("PIISHIELD") == ("http://x", "key", "proj-1")
