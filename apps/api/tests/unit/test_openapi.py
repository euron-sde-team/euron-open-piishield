"""Unit tests for the OpenAPI export used by `piishield openapi` (docs/api/openapi.yaml),
so other agents building the SDKs and dashboard have a drift-free contract."""

from __future__ import annotations

from piishield.openapi import spec, to_yaml


def test_spec_includes_every_domain_router() -> None:
    document = spec()
    paths = document["paths"]
    assert "/healthz" in paths
    assert "/api/v1/auth/signup" in paths
    assert "/api/v1/protect/text" in paths
    assert "/api/v1/vault/detokenize" in paths
    assert "/api/v1/ai-gateway/protect" in paths
    assert "/api/v1/audit" in paths
    assert document["info"]["title"] == "Euron Open PIIShield"


def test_spec_vault_response_never_declares_a_sealed_value_field() -> None:
    """A structural check on the contract itself: the vault's schemas never define a
    field that could carry an encrypted blob (AC6, enforced at the schema level)."""
    document = spec()
    schemas = document["components"]["schemas"]
    for name, schema in schemas.items():
        if "vault" in name.lower() or "Detokenize" in name:
            properties = schema.get("properties", {})
            assert "sealed_value" not in properties
            assert "ciphertext" not in properties


def test_to_yaml_round_trips_the_spec() -> None:
    import yaml

    document = spec()
    rendered = to_yaml(document)
    assert "openapi:" in rendered
    parsed = yaml.safe_load(rendered)
    assert parsed["info"]["title"] == document["info"]["title"]
