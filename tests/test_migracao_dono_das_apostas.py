"""Migração 20261104_0011: as apostas que já existiam ganham dono (ADR 0004).

Mede no PostgreSQL de teste, descendo uma revisão e subindo de novo: as
apostas sem dono vão para a conta `admin` de menor id, e, sem nenhuma conta
`admin`, a migração para sem mexer em nada. O `finally` de cada teste devolve
o banco à cabeça da cadeia, para os módulos seguintes.
"""

from __future__ import annotations

import pytest
from flask_migrate import downgrade, upgrade
from sqlalchemy import text

from app.extensions import db
from app.models import GeneratedBet, User

pytestmark = pytest.mark.banco

REVISAO_ANTERIOR = "20261028_0010_bet_confirmation"
LOTE = 980_000_001
NOMES = ["qa_migracao_operador", "qa_migracao_admin_1", "qa_migracao_admin_2"]


def _aposta_sem_dono() -> None:
    db.session.execute(
        text(
            "INSERT INTO generated_bets (generation_id, contest, numbers_csv, quantity, score, "
            f"created_at) VALUES ({LOTE}, {LOTE}, '1,2,3,4,5,6', 6, 0, now())"
        )
    )
    db.session.commit()


@pytest.fixture
def banco(app_com_banco):
    with app_com_banco.app_context():
        GeneratedBet.query.delete()
        User.query.filter(User.username.in_(NOMES)).delete(synchronize_session=False)
        db.session.commit()
        yield
        db.session.rollback()
        upgrade()
        db.session.execute(text(f"DELETE FROM generated_bets WHERE generation_id = {LOTE}"))
        User.query.filter(User.username.in_(NOMES)).delete(synchronize_session=False)
        db.session.commit()


def test_apostas_antigas_vao_para_o_admin_de_menor_id(banco):
    for nome, papel in zip(NOMES, ["operador", "admin", "admin"], strict=True):
        db.session.add(User(username=nome, role=papel, password_hash="sintetico"))
    db.session.commit()
    esperado = db.session.execute(
        text("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")
    ).scalar_one()
    # A migração roda em outra conexão e altera `users`: uma leitura desta
    # sessão ainda aberta a faria esperar para sempre.
    db.session.commit()

    downgrade(revision=REVISAO_ANTERIOR)
    _aposta_sem_dono()
    upgrade()

    dono = db.session.execute(
        text(f"SELECT owner_id FROM generated_bets WHERE generation_id = {LOTE}")
    ).scalar_one()
    assert dono == esperado


def test_sem_admin_a_migracao_para_sem_mexer_em_nada(banco, capfd):
    db.session.add(User(username=NOMES[0], role="operador", password_hash="sintetico"))
    # Rebaixa por um instante qualquer admin deixado no banco de teste; o
    # `finally` devolve o papel antes de qualquer outra coisa.
    admins = [linha[0] for linha in db.session.execute(text("SELECT id FROM users WHERE role = 'admin'"))]
    db.session.execute(text("UPDATE users SET role = 'operador' WHERE role = 'admin'"))
    db.session.commit()
    try:
        downgrade(revision=REVISAO_ANTERIOR)
        _aposta_sem_dono()
        # O Flask-Migrate escreve o erro da revisão no stderr (handler do
        # Alembic, fora do `logging` do pytest) e encerra com código 1, que é
        # o que o serviço `migrate` do Compose devolve no deploy.
        with pytest.raises(SystemExit):
            upgrade()
        assert "nenhuma conta admin" in capfd.readouterr().err
        versao = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        db.session.commit()
        assert versao == REVISAO_ANTERIOR
    finally:
        db.session.rollback()
        if admins:
            db.session.execute(
                text("UPDATE users SET role = 'admin' WHERE id = ANY(:ids)"), {"ids": admins}
            )
        db.session.execute(text(f"DELETE FROM generated_bets WHERE generation_id = {LOTE}"))
        db.session.commit()
