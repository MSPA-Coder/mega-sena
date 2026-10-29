"""Exercita sessão e CSRF reais, com falha apenas na fronteira do driver."""

import re
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.extensions import db
from app.models import AuditEvent, GeneratedBet, User

pytestmark = pytest.mark.banco


def _csrf(response):
    return re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    ).group(1)


def test_failed_audit_on_authenticated_confirmation_does_not_save_bet(app_com_banco):
    with app_com_banco.app_context():
        user = User(username="http_atomic_synthetic", role="admin")
        user.set_password("Synthetic-password-20261018")
        db.session.add(user)
        db.session.commit()
        user_id, engine = user.id, db.engine
        before = GeneratedBet.query.count()
    client = app_com_banco.test_client()
    response = client.post(
        "/login",
        data={
            "username": "http_atomic_synthetic",
            "password": "Synthetic-password-20261018",
            "csrf_token": _csrf(client.get("/login")),
        },
    )
    assert response.status_code == 302
    token = _csrf(client.get("/bets"))

    def fail_audit(_connection, _cursor, _statement, _parameters, context, _many):
        table = getattr(getattr(context.compiled, "statement", None), "table", None)
        if context.isinsert and table is not None and table.name == "audit_events":
            raise RuntimeError("auditoria indisponível (sintético)")

    event.listen(engine, "before_cursor_execute", fail_audit)
    try:
        with pytest.raises(RuntimeError, match="auditoria indisponível"):
            client.post(
                "/bets",
                data={
                    "action": "save",
                    "contest": "9999",
                    "quantity": "6",
                    "amount": "1",
                    "bet": "37,41,43,47,53,59",
                    "csrf_token": token,
                    "confirmation_token": str(uuid4()),
                },
            )
    finally:
        event.remove(engine, "before_cursor_execute", fail_audit)
    try:
        with app_com_banco.app_context():
            assert GeneratedBet.query.count() == before
            assert (
                AuditEvent.query.filter_by(
                    action="bets.save", actor_user_id=user_id, success=True
                ).count()
                == 0
            )
    finally:
        with app_com_banco.app_context():
            db.session.rollback()
            AuditEvent.query.filter_by(actor_user_id=user_id).delete()
            db.session.delete(db.session.get(User, user_id))
            db.session.commit()
