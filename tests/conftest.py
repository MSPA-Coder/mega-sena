from __future__ import annotations

import pytest

from app import db
from tests.support import make_app


_CATEGORY_MARKERS = {
    "tests/unit/": ("business_rule", "critical"),
    "tests/integration/": ("persistence", "critical"),
    "tests/web/": ("contract",),
    "tests/integration/test_migrations.py": ("migration", "critical"),
    "tests/integration/test_legacy_migration_sequence.py": ("migration", "critical"),
    "tests/integration/test_test_database_safety.py": ("migration", "critical"),
    "tests/web/test_security.py": ("security", "critical"),
    "tests/web/test_htmx.py": ("ui_smoke",),
    "tests/web/test_design_system.py": ("ui_smoke",),
}


def pytest_collection_modifyitems(config, items):
    """Classifica cada teste por risco/finalidade usando seu caminho estável."""
    for item in items:
        path = item.path.as_posix()
        relative_path = path[path.index("tests/") :] if "tests/" in path else path
        markers = set()
        for prefix, categories in _CATEGORY_MARKERS.items():
            if relative_path.startswith(prefix):
                markers.update(categories)
        if not markers:
            raise pytest.UsageError(f"Teste sem classificação de risco/finalidade: {relative_path}")
        for category in markers:
            item.add_marker(getattr(pytest.mark, category))


@pytest.fixture
def app():
    """Aplicação de teste sobre PostgreSQL descartável (ver tests/support.py).

    Não é usada pela maioria dos testes, que chamam `make_app()` diretamente;
    fica disponível para casos que preferem injeção via fixture do pytest.
    """
    application = make_app()
    yield application
    with application.app_context():
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()
