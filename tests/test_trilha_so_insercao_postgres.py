"""A trilha `audit_events` aceita inserção de quem não é dono (revisão 0013).

A suíte roda como superusuário (o papel administrativo), que o gatilho deixa
passar de propósito. Para medir o que o papel da aplicação enfrenta, o teste
cria um papel comum, sem login, com o mesmo DML que o `db-provision` concede, e
assume esse papel com `SET LOCAL ROLE`.
"""

from uuid import uuid4

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import delete, text
from sqlalchemy.exc import DBAPIError

from app.extensions import db
from app.models import AuditEvent, User

pytestmark = pytest.mark.banco


@pytest.fixture
def papel_comum(app_com_banco):
    nome = "trilha_t_" + uuid4().hex[:10]
    with app_com_banco.app_context():
        db.session.execute(text(f'CREATE ROLE "{nome}" NOLOGIN'))
        db.session.execute(
            text(
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON audit_events, users TO "{nome}"'
            )
        )
        db.session.execute(text(f'GRANT USAGE ON SEQUENCE audit_events_id_seq TO "{nome}"'))
        db.session.commit()
    yield nome
    with app_com_banco.app_context():
        db.session.rollback()
        db.session.execute(text(f'DROP OWNED BY "{nome}"'))
        db.session.execute(text(f'DROP ROLE "{nome}"'))
        db.session.commit()


@pytest.fixture
def evento(app_com_banco):
    with app_com_banco.app_context():
        usuario = User(username="trilha-i-" + uuid4().hex[:10], role="operador")
        usuario.set_password("Senha-sintetica-trilha-2026")
        db.session.add(usuario)
        db.session.flush()
        registro = AuditEvent(
            actor_user_id=usuario.id, action="teste.trilha", entity="user", success=True
        )
        db.session.add(registro)
        db.session.commit()
        ids = (registro.id, usuario.id)
    yield ids
    with app_com_banco.app_context():
        db.session.rollback()
        db.session.execute(delete(AuditEvent).where(AuditEvent.id == ids[0]))
        db.session.execute(delete(User).where(User.id == ids[1]))
        db.session.commit()


def _como(papel: str, sql: str, **params):
    db.session.execute(text(f'SET LOCAL ROLE "{papel}"'))
    return db.session.execute(text(sql), params)


def test_papel_comum_insere_mas_nao_altera_nem_apaga(app_com_banco, papel_comum, evento):
    evento_id, usuario_id = evento
    with app_com_banco.app_context():
        _como(
            papel_comum,
            "INSERT INTO audit_events (actor_user_id, action, entity, success, context, occurred_at)"
            " VALUES (:u, 'teste.trilha.novo', 'user', true, '{}', now())",
            u=usuario_id,
        )
        db.session.rollback()

        with pytest.raises(DBAPIError, match="aceita apenas insercao"):
            _como(papel_comum, "UPDATE audit_events SET success = false WHERE id = :i", i=evento_id)
        db.session.rollback()

        with pytest.raises(DBAPIError, match="aceita apenas insercao"):
            _como(papel_comum, "DELETE FROM audit_events WHERE id = :i", i=evento_id)
        db.session.rollback()

        assert db.session.get(AuditEvent, evento_id) is not None


def test_anular_o_ator_continua_possivel_e_so_isso(app_com_banco, papel_comum, evento):
    evento_id, _ = evento
    with app_com_banco.app_context():
        with pytest.raises(DBAPIError, match="aceita apenas insercao"):
            _como(
                papel_comum,
                "UPDATE audit_events SET actor_user_id = NULL, success = false WHERE id = :i",
                i=evento_id,
            )
        db.session.rollback()

        _como(papel_comum, "UPDATE audit_events SET actor_user_id = NULL WHERE id = :i", i=evento_id)
        db.session.commit()
        assert db.session.get(AuditEvent, evento_id).actor_user_id is None


def test_o_administrador_ainda_corrige_e_expurga(app_com_banco, evento):
    evento_id, _ = evento
    with app_com_banco.app_context():
        db.session.execute(
            text("UPDATE audit_events SET success = false WHERE id = :i"), {"i": evento_id}
        )
        db.session.commit()
        assert db.session.get(AuditEvent, evento_id).success is False


def test_revisoes_0012_e_0013_sobem_e_descem(app_com_banco) -> None:
    def catalogo():
        with app_com_banco.app_context():
            restricao = db.session.execute(
                text("SELECT count(*) FROM pg_constraint WHERE conname = 'uq_users_username'")
            ).scalar_one()
            gatilho = db.session.execute(
                text("SELECT count(*) FROM pg_trigger WHERE tgname = 'audit_events_somente_insercao'")
            ).scalar_one()
            db.session.rollback()
            return restricao, gatilho

    assert catalogo() == (0, 1)
    with app_com_banco.app_context():
        try:
            downgrade(revision="20261104_0011_owner_per_user")
            assert catalogo() == (1, 0)
        finally:
            upgrade()
            upgrade()  # idempotente: repetir não muda nada
    assert catalogo() == (0, 1)
