"""Recursive leaf-string scanning and protection for JSON payloads (AC7).

``walk_strings`` yields every string leaf with a JSON-Pointer-like path; the protection
service scans and protects each leaf independently (so a finding's span is always local
to its own leaf string, simple and unambiguous) and ``rebuild`` reassembles the exact
original structure (same keys, same nesting, same array order and length) with only the
leaf strings replaced. Non-string leaves (numbers, booleans, null) pass through untouched.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

MAX_DEPTH = 20
MAX_ARRAY_ITEMS = 10_000


def walk_strings(value: Any, path: str = "$", depth: int = 0) -> Iterator[tuple[str, str]]:
    """Yields (path, leaf_string) for every string found at any depth."""
    if depth > MAX_DEPTH:
        return
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from walk_strings(item, f"{path}.{key}", depth + 1)
    elif isinstance(value, list):
        for i, item in enumerate(value[:MAX_ARRAY_ITEMS]):
            yield from walk_strings(item, f"{path}[{i}]", depth + 1)


def rebuild(value: Any, replacements: dict[str, str], path: str = "$", depth: int = 0) -> Any:
    """A structurally identical copy of ``value`` with each leaf string at ``path`` in
    ``replacements`` swapped in; every other value (numbers, booleans, null, dict/list
    shape, key order, array order and length) is preserved exactly."""
    if depth > MAX_DEPTH:
        return value
    if isinstance(value, str):
        return replacements.get(path, value)
    if isinstance(value, dict):
        return {
            key: rebuild(item, replacements, f"{path}.{key}", depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            rebuild(item, replacements, f"{path}[{i}]", depth + 1)
            for i, item in enumerate(value[:MAX_ARRAY_ITEMS])
        ]
    return value
