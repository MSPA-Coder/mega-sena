"""Correção das apostas gravadas com diversidade zero, sem tocar em fechamentos."""

from itertools import combinations

import pytest

from app.bets.commands import recalcular_scores_zerados
from app.bets.service import prepare_closure_bets
from app.models import GeneratedBet, User, db

GERACAO_DEFEITUOSA = 9001
GERACAO_CORRETA = 9002
GERACAO_FECHAMENTO = 9003


@pytest.fixture
def apostas(sessao, monkeypatch):
    # A função grava com commit; aqui a transação do teste é quem é desfeita.
    monkeypatch.setattr(db.session, "commit", db.session.flush)
    monkeypatch.setattr(db.session, "rollback", lambda: None)
    dono = User(username="dono-diversidade", role="admin")
    dono.set_password("Senha-sintetica-do-teste-2026!")
    sessao.add(dono)
    sessao.flush()

    def adicionar(geracao, numeros, score):
        sessao.add(GeneratedBet(owner_id=dono.id, generation_id=geracao, quantity=6,
                                numbers_csv=",".join(map(str, numeros)), score=score))

    adicionar(GERACAO_DEFEITUOSA, [1, 2, 3, 4, 5, 6], 0)
    adicionar(GERACAO_DEFEITUOSA, [1, 2, 3, 40, 50, 60], 0)
    adicionar(GERACAO_CORRETA, [7, 8, 9, 10, 11, 12], 1.0)
    adicionar(GERACAO_CORRETA, [7, 8, 9, 41, 51, 59], 0)
    for combinacao in combinations([11, 12, 13, 14, 15, 16, 17], 6):
        adicionar(GERACAO_FECHAMENTO, combinacao, 0)
    sessao.flush()
    return sessao


def _scores(sessao, geracao):
    return [b.score for b in sessao.scalars(
        db.select(GeneratedBet).where(GeneratedBet.generation_id == geracao).order_by(GeneratedBet.id)
    )]


def test_corrige_so_a_geracao_toda_zerada(apostas):
    assert recalcular_scores_zerados(aplicar=True) == (1, 2)
    assert _scores(apostas, GERACAO_DEFEITUOSA) == [1.0, 0.5]
    assert _scores(apostas, GERACAO_CORRETA) == [1.0, 0]


def test_fechamento_continua_com_zero(apostas):
    recalcular_scores_zerados(aplicar=True)
    assert set(_scores(apostas, GERACAO_FECHAMENTO)) == {0}
    assert all(b.score == 0 for b in prepare_closure_bets(range(1, 8)))
