"""ADR 0048's addendum: CORS_ALLOWED_ORIGINS is space-separated, not a JSON
array - a real deploy crashed on the JSON array's own internal comma
colliding with how the deploy workflow joins environment variables (see
that addendum for the full story). Settings itself needs no database, so
these construct it directly rather than going through any DB-backed
fixture. `monkeypatch.setenv`, not an init kwarg - real production sets
this via an actual environment variable, and `_env_file=None` keeps each
case isolated from whatever a local `.env` happens to have.
"""

import pytest

from lorenzo_api.config import Settings


def test_cors_origins_space_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://a.example.com https://b.example.com")
    settings = Settings(_env_file=None)
    assert settings.cors_allowed_origins == ["https://a.example.com", "https://b.example.com"]


def test_cors_origins_single(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://a.example.com")
    settings = Settings(_env_file=None)
    assert settings.cors_allowed_origins == ["https://a.example.com"]


def test_cors_origins_unset_defaults_to_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    settings = Settings(_env_file=None)
    assert settings.cors_allowed_origins == []


def test_cors_origins_empty_string_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real shape an unset GitHub Actions variable arrives as - an
    empty string, not an absent key.
    """
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "")
    settings = Settings(_env_file=None)
    assert settings.cors_allowed_origins == []


def test_cors_origins_legacy_json_array_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backward compatible with the original ADR 0048 format - an existing
    .env still using it keeps working unchanged.
    """
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://a.example.com","https://b.example.com"]')
    settings = Settings(_env_file=None)
    assert settings.cors_allowed_origins == ["https://a.example.com", "https://b.example.com"]


def test_cors_origins_legacy_json_empty_array_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "[]")
    settings = Settings(_env_file=None)
    assert settings.cors_allowed_origins == []
