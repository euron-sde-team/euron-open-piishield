"""Unit tests for JSON leaf-string recursion and structure-preserving rebuild (AC7)."""

from __future__ import annotations

from piishield.protection.json_walk import rebuild, walk_strings


def test_ac7_walk_strings_finds_every_leaf_with_a_path() -> None:
    payload = {"name": "Ananya", "tags": ["a", "b"], "nested": {"email": "x@y.com"}}
    found = dict(walk_strings(payload))
    assert found["$.name"] == "Ananya"
    assert found["$.tags[0]"] == "a"
    assert found["$.tags[1]"] == "b"
    assert found["$.nested.email"] == "x@y.com"


def test_ac7_walk_strings_skips_non_string_leaves() -> None:
    payload = {"age": 30, "active": True, "note": None}
    assert list(walk_strings(payload)) == []


def test_ac7_rebuild_preserves_keys_nesting_and_array_order() -> None:
    payload = {"a": "one", "b": [{"c": "two"}, {"c": "three"}], "d": 42, "e": None}
    replacements = {"$.a": "ONE", "$.b[0].c": "TWO", "$.b[1].c": "THREE"}
    rebuilt = rebuild(payload, replacements)
    assert rebuilt == {"a": "ONE", "b": [{"c": "TWO"}, {"c": "THREE"}], "d": 42, "e": None}
    # Same keys in the same order, same array length and order; only leaf strings changed.
    assert isinstance(rebuilt, dict)
    assert list(rebuilt.keys()) == list(payload.keys())
    rebuilt_b = rebuilt["b"]
    payload_b = payload["b"]
    assert isinstance(rebuilt_b, list)
    assert isinstance(payload_b, list)
    assert len(rebuilt_b) == len(payload_b)


def test_ac7_rebuild_without_matching_replacement_keeps_original() -> None:
    payload = {"a": "unchanged"}
    assert rebuild(payload, {}) == payload


def test_ac7_round_trip_identity_when_nothing_found() -> None:
    payload = {"x": [1, 2, {"y": "z"}], "w": None}
    # Rebuild with an empty replacement set is the identity transform.
    assert rebuild(payload, {}) == payload
