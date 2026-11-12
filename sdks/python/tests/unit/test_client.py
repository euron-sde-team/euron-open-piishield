"""The sync client with mocked HTTP: request building, response parsing, exception mapping."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx

from euron_piishield import (
    APIError,
    PIIShield,
    PolicyViolationError,
    VaultPermissionError,
)
from euron_piishield.errors import ConnectionError as PIIShieldConnectionError

from .helpers import (
    API_KEY,
    BASE,
    PROJECT_ID,
    error_body,
    finding,
    protect_text_response,
    scan_response,
)


@pytest.fixture
def api() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=BASE, assert_all_called=False) as router:
        yield router


@pytest.fixture
def shield() -> Iterator[PIIShield]:
    client = PIIShield(BASE, API_KEY, PROJECT_ID)
    yield client
    client.close()


def _body(request: httpx.Request) -> Any:
    return json.loads(request.content)


def test_options_are_checked() -> None:
    with pytest.raises(ValueError, match="http"):
        PIIShield("piishield.test", API_KEY, PROJECT_ID)
    with pytest.raises(ValueError, match="api_key"):
        PIIShield(BASE, "", PROJECT_ID)


def test_scan_calls_dedicated_scan_route_and_parses_findings(
    api: respx.MockRouter, shield: PIIShield
) -> None:
    route = api.post("/api/v1/detectors/scan").mock(
        return_value=httpx.Response(
            200,
            json=scan_response(finding("contact", 0, 10, 0.95, recognizer="email")),
        )
    )
    result = shield.scan("rahul@x.com")
    sent = _body(route.calls.last.request)
    assert sent == {"project_id": PROJECT_ID, "text": "rahul@x.com"}
    assert route.calls.last.request.headers["authorization"] == f"Bearer {API_KEY}"
    assert len(result.findings) == 1
    f = result.findings[0]
    assert f.category == "contact" and f.start == 0 and f.end == 10 and f.confidence == 0.95
    assert f.checksum_valid is None
    assert f.recognizer == "email"


def test_scan_json_wraps_payload(api: respx.MockRouter, shield: PIIShield) -> None:
    route = api.post("/api/v1/protect/json").mock(
        return_value=httpx.Response(
            200, json={"protected": {}, "findings": [], "review_count": 0, "scope_id": "s"}
        )
    )
    payload = {"customer": {"email": "a@b.com"}, "tags": ["x", "y"]}
    shield.scan_json(payload)
    sent = _body(route.calls.last.request)
    assert sent["payload"] == payload
    assert sent["project_id"] == PROJECT_ID


def test_mask_sends_method_overrides_and_project_id(
    api: respx.MockRouter, shield: PIIShield
) -> None:
    route = api.post("/api/v1/protect/text").mock(
        return_value=httpx.Response(200, json=protect_text_response("Hello [REDACTED]"))
    )
    result = shield.mask("Hello Rahul", method="redact", categories=["personal"])
    sent = _body(route.calls.last.request)
    assert sent == {
        "project_id": PROJECT_ID,
        "text": "Hello Rahul",
        "method_overrides": {"personal": "redact"},
    }
    assert result.protected_text == "Hello [REDACTED]"


def test_mask_default_method_is_full_mask(api: respx.MockRouter, shield: PIIShield) -> None:
    route = api.post("/api/v1/protect/text").mock(
        return_value=httpx.Response(200, json=protect_text_response("***"))
    )
    shield.mask("secret", categories=["contact"])
    assert _body(route.calls.last.request)["method_overrides"] == {"contact": "full_mask"}


@pytest.mark.parametrize(
    ("method_name", "extra_kwargs", "expected_method"),
    [
        ("redact", {}, "redact"),
        ("anonymize", {}, "full_mask"),
        ("tokenize", {"scope_id": "req-1"}, "tokenize"),
    ],
)
def test_convenience_wrappers_apply_the_right_method_override(
    api: respx.MockRouter,
    shield: PIIShield,
    method_name: str,
    extra_kwargs: dict[str, Any],
    expected_method: str,
) -> None:
    route = api.post("/api/v1/protect/text").mock(
        return_value=httpx.Response(200, json=protect_text_response("x"))
    )
    getattr(shield, method_name)("some text", **extra_kwargs, categories=["contact"])
    sent = _body(route.calls.last.request)
    assert sent["method_overrides"] == {"contact": expected_method}
    assert sent["text"] == "some text"
    if "scope_id" in extra_kwargs:
        assert sent["scope_id"] == extra_kwargs["scope_id"]


def test_tokenize_same_scope_contract_is_forwarded_consistently(
    api: respx.MockRouter, shield: PIIShield
) -> None:
    """AC4: the SDK must send the same scope_id on both calls so the server can keep
    placeholders consistent; this test locks in that the SDK never drops or rewrites it."""
    route = api.post("/api/v1/protect/text").mock(
        side_effect=[
            httpx.Response(200, json=protect_text_response("[EMAIL_001]", scope_id="session-42")),
            httpx.Response(200, json=protect_text_response("[EMAIL_001]", scope_id="session-42")),
        ]
    )
    first = shield.tokenize("a@example.com", scope_id="session-42")
    second = shield.tokenize("a@example.com", scope_id="session-42")
    assert _body(route.calls[0].request)["scope_id"] == "session-42"
    assert _body(route.calls[1].request)["scope_id"] == "session-42"
    assert first.protected_text == second.protected_text == "[EMAIL_001]"
    assert first.scope_id == second.scope_id == "session-42"


def test_detokenize_sends_placeholder_and_scope(api: respx.MockRouter, shield: PIIShield) -> None:
    route = api.post("/api/v1/vault/detokenize").mock(
        return_value=httpx.Response(
            200, json={"placeholder": "[EMAIL_001]", "value": "a@example.com", "category": "email"}
        )
    )
    result = shield.detokenize("[EMAIL_001]", "session-42")
    sent = _body(route.calls.last.request)
    assert sent == {
        "project_id": PROJECT_ID,
        "placeholder": "[EMAIL_001]",
        "scope_id": "session-42",
    }
    assert result.value == "a@example.com"
    assert result.category == "email"


def test_detokenize_403_vault_access_required_raises_vault_permission_error(
    api: respx.MockRouter, shield: PIIShield
) -> None:
    api.post("/api/v1/vault/detokenize").mock(
        return_value=httpx.Response(403, json=error_body("vault_access_required", "forbidden"))
    )
    with pytest.raises(VaultPermissionError) as exc_info:
        shield.detokenize("[EMAIL_001]", "session-42")
    # Never a hint of the original value in the exception.
    assert "@" not in str(exc_info.value)
    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "vault_access_required"


def test_detokenize_403_is_not_a_plain_api_error_type(
    api: respx.MockRouter, shield: PIIShield
) -> None:
    """Callers must be able to catch VaultPermissionError specifically, not just APIError."""
    api.post("/api/v1/vault/detokenize").mock(
        return_value=httpx.Response(403, json=error_body("vault_access_required"))
    )
    try:
        shield.detokenize("[EMAIL_001]", "s")
    except VaultPermissionError:
        pass
    except APIError:
        pytest.fail(
            "a 403 vault_access_required must raise VaultPermissionError, not plain APIError"
        )


def test_other_403_codes_stay_plain_api_error(api: respx.MockRouter, shield: PIIShield) -> None:
    """A 403 with a DIFFERENT code than vault_access_required is a normal APIError."""
    api.post("/api/v1/detectors/scan").mock(
        return_value=httpx.Response(403, json=error_body("insufficient_role"))
    )
    with pytest.raises(APIError) as exc_info:
        shield.scan("x")
    assert not isinstance(exc_info.value, VaultPermissionError)


def test_policy_violation_raises_typed_exception(api: respx.MockRouter, shield: PIIShield) -> None:
    api.post("/api/v1/protect/text").mock(
        return_value=httpx.Response(
            422, json=error_body("required_category_unmasked", "financial category must be masked")
        )
    )
    with pytest.raises(PolicyViolationError):
        shield.mask("card 4111111111111111")


def test_generic_error_maps_to_api_error(api: respx.MockRouter, shield: PIIShield) -> None:
    api.post("/api/v1/detectors/scan").mock(
        return_value=httpx.Response(400, json=error_body("validation_error"))
    )
    with pytest.raises(APIError) as exc_info:
        shield.scan("x")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "validation_error"


def test_503_dependency_unavailable_maps_to_connection_error(
    api: respx.MockRouter, shield: PIIShield
) -> None:
    """The server's contract: a dependency being down is a clear, retryable 503, never a
    response that silently omits findings. The SDK surfaces this as a connection-shaped
    failure so callers that retry on ConnectionError also retry here."""
    api.post("/api/v1/detectors/scan").mock(
        return_value=httpx.Response(503, json=error_body("dependency_unavailable"))
    )
    with pytest.raises(PIIShieldConnectionError):
        shield.scan("x")


def test_transport_failure_raises_connection_error(shield: PIIShield) -> None:
    with respx.mock(base_url=BASE) as router:
        router.post("/api/v1/detectors/scan").mock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(PIIShieldConnectionError):
            shield.scan("x")


def test_protect_separates_protected_text_from_scope_id(
    api: respx.MockRouter, shield: PIIShield
) -> None:
    api.post("/api/v1/ai-gateway/protect").mock(
        return_value=httpx.Response(
            200,
            json={
                "protected_prompt": "My PAN is [PAN_001]. Explain my tax record.",
                "scope_id": "scope-abc123",
                "findings": [finding("pan", 10, 20, 0.9)],
            },
        )
    )
    result = shield.protect("My PAN is ABCDE1234F. Explain my tax record.")
    assert "ABCDE1234F" not in result.protected_text
    assert result.protected_text == "My PAN is [PAN_001]. Explain my tax record."
    assert result.scope_id == "scope-abc123"


def test_restore_sends_scope_id_and_model_response(
    api: respx.MockRouter, shield: PIIShield
) -> None:
    route = api.post("/api/v1/ai-gateway/restore").mock(
        return_value=httpx.Response(
            200,
            json={"restored_response": "Your PAN ABCDE1234F is valid.", "placeholders_restored": 1},
        )
    )
    result = shield.restore("scope-abc123", "Your PAN [PAN_001] is valid.")
    assert _body(route.calls.last.request) == {
        "project_id": PROJECT_ID,
        "scope_id": "scope-abc123",
        "model_response": "Your PAN [PAN_001] is valid.",
    }
    assert result.restored_text == "Your PAN ABCDE1234F is valid."
    assert result.placeholders_restored == 1


def test_get_policy_parses_response(api: respx.MockRouter, shield: PIIShield) -> None:
    api.get(f"/api/v1/projects/{PROJECT_ID}/policy").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "p1",
                "project_id": PROJECT_ID,
                "required_categories": ["financial"],
                "masking_method": {"financial": "tokenize"},
                "partial_mask_reveal": 4,
                "confidence_threshold": 0.6,
                "retention_days": 90,
            },
        )
    )
    policy = shield.get_policy()
    assert policy.required_categories == ["financial"]
    assert policy.masking_method == {"financial": "tokenize"}


def test_set_policy_sends_put_with_body(api: respx.MockRouter, shield: PIIShield) -> None:
    route = api.put(f"/api/v1/projects/{PROJECT_ID}/policy").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "p1",
                "project_id": PROJECT_ID,
                "required_categories": ["financial"],
                "masking_method": {},
                "partial_mask_reveal": 4,
                "confidence_threshold": 0.6,
                "retention_days": 90,
            },
        )
    )
    shield.set_policy(required_categories=["financial"])
    sent = _body(route.calls.last.request)
    assert sent["required_categories"] == ["financial"]


def test_get_audit_logs_never_includes_raw_pii_by_contract(
    api: respx.MockRouter, shield: PIIShield
) -> None:
    """The client cannot enforce AC11 server side, but its model must not invent a field
    that could carry a raw value: AuditLogEntry has no 'value' or 'original' field."""
    api.get("/api/v1/audit").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "log1",
                        "created_at": "2026-11-12T00:00:00Z",
                        "actor_kind": "api_key",
                        "actor_label": "api-key:ci",
                        "action": "protect_text",
                        "project_id": PROJECT_ID,
                        "finding_count": 2,
                        "categories": ["email", "phone"],
                        "details": {},
                    }
                ],
                "next_cursor": None,
            },
        )
    )
    page = shield.get_audit_logs()
    assert page.items[0].action == "protect_text"
    assert not hasattr(page.items[0], "value")
    assert not hasattr(page.items[0], "original")


def test_scan_database_sends_engine_and_table(api: respx.MockRouter, shield: PIIShield) -> None:
    route = api.post("/api/v1/database-scan").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "scan1",
                "table_name": "customers",
                "rows_sampled": 200,
                "columns": [
                    {"column": "email", "category": "email", "confidence": 0.9, "sample_hits": 180}
                ],
            },
        )
    )
    result = shield.scan_database("postgresql://x", "customers", "postgres")
    sent = _body(route.calls.last.request)
    assert sent["table_name"] == "customers" and sent["engine"] == "postgres"
    assert result.columns[0].column == "email"
