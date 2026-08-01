from __future__ import annotations

import pytest

from tests.support import TEST_DATABASE_URL_ENV, get_test_database_url


def test_test_database_url_never_falls_back_to_application_database(monkeypatch) -> None:
    """A suíte deve falhar antes de tocar o banco operacional por engano."""
    monkeypatch.delenv(TEST_DATABASE_URL_ENV, raising=False)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://app:secret@postgres:5432/mega_sena"
    )

    with pytest.raises(RuntimeError, match="TEST_DATABASE_URL não definida"):
        get_test_database_url()


def test_test_database_url_rejects_same_database_with_equivalent_driver(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        TEST_DATABASE_URL_ENV,
        "postgresql+psycopg://tester:test@postgres:5432/mega_sena_test",
    )
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://app:other@postgres/mega_sena_test",
    )

    with pytest.raises(RuntimeError, match="mesmo banco"):
        get_test_database_url()


@pytest.mark.parametrize(
    "database_name",
    ["postgres", "mega_sena", "production"],
)
def test_test_database_url_requires_explicit_disposable_name(
    monkeypatch, database_name: str
) -> None:
    monkeypatch.setenv(
        TEST_DATABASE_URL_ENV,
        f"postgresql+psycopg://tester:test@postgres:5432/{database_name}",
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="termine em '_test'"):
        get_test_database_url()


def test_test_database_url_accepts_separate_disposable_database(monkeypatch) -> None:
    test_url = "postgresql+psycopg://tester:test@postgres:5432/mega_sena_test"
    monkeypatch.setenv(TEST_DATABASE_URL_ENV, test_url)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://app:secret@postgres:5432/mega_sena"
    )

    assert get_test_database_url() == test_url
