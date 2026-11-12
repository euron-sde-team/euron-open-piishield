import pytest

from piishield.core.config import Settings


def test_cors_origins_parses_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5510,http://127.0.0.1:5510")
    settings = Settings()
    assert settings.cors_origins == ["http://localhost:5510", "http://127.0.0.1:5510"]


def test_cors_origins_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    settings = Settings()
    assert settings.cors_origins == ["http://localhost:5510"]
