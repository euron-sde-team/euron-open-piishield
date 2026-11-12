"""Unit tests for the `piishield` CLI's argument parsing and its database-free
subcommand (`openapi`). `serve`/`migrate`/`seed-demo`/`create-admin` need a real database
or a running server and are exercised through `make demo`/`make up`, not here."""

from __future__ import annotations

import pytest

from piishield.cli import main


def test_openapi_subcommand_prints_yaml(capsys: pytest.CaptureFixture[str]) -> None:
    main(["openapi"])
    captured = capsys.readouterr()
    assert "openapi:" in captured.out
    assert "Euron Open PIIShield" in captured.out


def test_missing_subcommand_exits_nonzero() -> None:
    with pytest.raises(SystemExit):
        main([])


def test_unknown_subcommand_exits_nonzero() -> None:
    with pytest.raises(SystemExit):
        main(["not-a-real-command"])


def test_serve_subcommand_help_lists_host_and_port_flags(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Argument parsing only: ``--help`` exits 0 without starting uvicorn, and the usage
    text documents the ``--host``/``--port`` flags ``_serve`` reads."""
    with pytest.raises(SystemExit) as exc_info:
        main(["serve", "--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "--host" in captured.out
    assert "--port" in captured.out


def test_create_admin_requires_email_flag() -> None:
    with pytest.raises(SystemExit):
        main(["create-admin"])
