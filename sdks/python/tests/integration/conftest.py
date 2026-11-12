"""Integration fixtures: a real, running PIIShield API.

Set ``PIISHIELD_API_URL``, ``PIISHIELD_API_KEY`` and ``PIISHIELD_PROJECT_ID`` to run these
tests (for example ``http://localhost:5530``, a write-scoped key created under
``POST /api/v1/auth/keys``, and that key's project). Tests are skipped, not failed, when
unset, matching the sibling projects' pattern.

These exercise the SDK against the backend's real wire format. If the backend has
refined any field name since this reconciliation pass (see both READMEs' "Wire format"
sections), several of these will fail until the SDK is updated again; that failure is the
point of keeping them separate from the unit suite.
"""

from __future__ import annotations

import os

import pytest

from euron_piishield import PIIShield

API_URL = os.environ.get("PIISHIELD_API_URL", "")
API_KEY = os.environ.get("PIISHIELD_API_KEY", "")
PROJECT_ID = os.environ.get("PIISHIELD_PROJECT_ID", "")

HERE = os.path.dirname(__file__)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    skip = pytest.mark.skip(
        reason="set PIISHIELD_API_URL, PIISHIELD_API_KEY and PIISHIELD_PROJECT_ID to run the integration tests"
    )
    for item in items:
        if str(item.path).startswith(HERE):
            item.add_marker(pytest.mark.integration)
            if not API_URL or not API_KEY or not PROJECT_ID:
                item.add_marker(skip)


@pytest.fixture
def shield() -> PIIShield:
    if not API_URL or not API_KEY or not PROJECT_ID:
        pytest.skip("set PIISHIELD_API_URL, PIISHIELD_API_KEY and PIISHIELD_PROJECT_ID")
    return PIIShield(API_URL, API_KEY, PROJECT_ID)
