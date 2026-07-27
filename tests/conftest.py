from __future__ import annotations

import pytest

from app import db
from tests.support import make_app


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
