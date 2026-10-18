"""Composição sintética montada SÓ no Compose browser, fora do runtime."""

import os
from datetime import date

from flask_migrate import upgrade

from app import create_app
from app.core.numbers import draw_parameters
from app.extensions import db
from app.models import AuditEvent, Draw, GeneratedBet, User

if os.environ.get("BROWSER_TEST_SERVER") != "1":
    raise RuntimeError("Use apenas compose.browser.yaml e PostgreSQL descartável.")

application = create_app({
    "TESTING": True,
    "SECRET_KEY": "synthetic-browser-only-never-operational",
    "TRUSTED_HOSTS": ["localhost", "127.0.0.1"],
    "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://browser:browser@browser-db:5432/browser_tests",
})
with application.app_context():
    upgrade()
    if User.query.count():
        raise RuntimeError("O banco browser precisa nascer vazio; recrie a pilha.")
    for region in ("br", "us"):
        user = User(username=f"browser-{region}", role="admin", regional_format=region)
        user.set_password("Synthetic-browser-only-2026!")
        db.session.add(user)
    for contest, numbers in enumerate(([1, 3, 5, 7, 9, 11], [2, 4, 6, 8, 10, 12]), 1):
        db.session.add(Draw(contest=contest, draw_date=date(2026, 1, contest),
            **{f"n{i}": n for i, n in enumerate(numbers, 1)}, **draw_parameters(numbers)))
    db.session.commit()


@application.get("/__browser__/state")
def state():
    # Sonda de teste, autenticada pelo gate padrão; não existe na imagem.
    return {"bets": GeneratedBet.query.count(),
            "creations": AuditEvent.query.filter_by(action="bets.save", success=True).count()}
