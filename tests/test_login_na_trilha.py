"""Login e falha de login entram na trilha de auditoria, sem dado sensível."""

import re
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.extensions import db
from app.models import AuditEvent, User

pytestmark = pytest.mark.banco

SENHA = "Senha-sintetica-trilha-2026"


def _csrf(resposta):
    return re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', resposta.get_data(as_text=True)
    ).group(1)


def _postar(app, nome, senha):
    cliente = app.test_client()
    cliente.environ_base["REMOTE_ADDR"] = "2001:db8::" + uuid4().hex[:4] + ":" + uuid4().hex[:4]
    token = _csrf(cliente.get("/login"))
    return cliente.post(
        "/login", data={"username": nome, "password": senha, "csrf_token": token}
    )


@pytest.fixture
def conta(app_com_banco):
    nome = "trilha-" + uuid4().hex[:10]
    with app_com_banco.app_context():
        usuario = User(username=nome, role="operador")
        usuario.set_password(SENHA)
        db.session.add(usuario)
        db.session.commit()
        ident = usuario.id
    yield nome, ident
    with app_com_banco.app_context():
        db.session.execute(delete(AuditEvent).where(AuditEvent.actor_user_id == ident))
        db.session.execute(delete(User).where(User.id == ident))
        db.session.commit()


def _eventos(app, ident):
    with app.app_context():
        linhas = db.session.scalars(
            select(AuditEvent)
            .where(AuditEvent.action == "auth.login", AuditEvent.actor_user_id == ident)
            .order_by(AuditEvent.id)
        ).all()
        return [(e.success, dict(e.context)) for e in linhas]


def test_falha_e_sucesso_ficam_na_trilha_sem_nome_nem_senha(app_com_banco, conta):
    nome, ident = conta
    assert _postar(app_com_banco, nome, "senha-errada-qualquer").status_code == 401
    assert _postar(app_com_banco, nome, SENHA).status_code == 302

    eventos = _eventos(app_com_banco, ident)
    assert [sucesso for sucesso, _ in eventos] == [False, True]
    for _, contexto in eventos:
        assert set(contexto) == {"route", "ip"}
        assert nome not in str(contexto)
        assert SENHA not in str(contexto)


def test_falha_de_usuario_inexistente_registra_sem_o_nome(app_com_banco):
    nome = "inexistente-" + uuid4().hex[:10]
    with app_com_banco.app_context():
        antes = db.session.scalar(
            select(db.func.max(AuditEvent.id)).where(AuditEvent.action == "auth.login")
        ) or 0
    assert _postar(app_com_banco, nome, "qualquer-senha-aqui").status_code == 401
    with app_com_banco.app_context():
        novos = db.session.scalars(
            select(AuditEvent).where(AuditEvent.action == "auth.login", AuditEvent.id > antes)
        ).all()
        try:
            assert len(novos) == 1
            assert novos[0].success is False
            assert novos[0].actor_user_id is None
            assert nome not in str(novos[0].context)
        finally:
            db.session.execute(delete(AuditEvent).where(AuditEvent.id.in_([e.id for e in novos])))
            db.session.commit()
