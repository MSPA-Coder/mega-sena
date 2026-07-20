from __future__ import annotations

import pytest

from app import db
from tests.support import make_app


@pytest.fixture
def app():
    application = make_app()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
