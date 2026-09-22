"""Histórico de gerações da tela de apostas, medido no PostgreSQL.

`list_recent_generations_with_bets` alimenta toda renderização da tela de
apostas. O contrato visível é: lotes do mais recente para o mais antigo, cada
um com suas apostas em ordem de gravação, cortado em
`MAX_RECENT_BETS_PER_GENERATION` e marcado como truncado quando passa disso.

O número de consultas também é contrato: a versão anterior fazia uma consulta
por lote (até 21 por tela). O teste prende a forma atual -- uma agregação e uma
busca das apostas -- para que um N+1 não volte sem ninguém notar.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event

from app.bets.service import (
    MAX_RECENT_BETS_PER_GENERATION,
    list_recent_generations_with_bets,
)
from app.models import GeneratedBet

pytestmark = pytest.mark.banco

# Datas no futuro põem estes lotes no topo do histórico mesmo que outro teste
# tenha deixado gerações gravadas no banco de teste.
_INICIO = datetime(2099, 1, 1, tzinfo=UTC)


def _lote(sessao, generation_id: int, quantidade: int, minutos: int) -> None:
    for indice in range(quantidade):
        sessao.add(
            GeneratedBet(
                generation_id=generation_id,
                quantity=6,
                numbers_csv=f"1,2,3,4,5,{6 + indice % 55}",
                score=0,
                created_at=_INICIO + timedelta(minutes=minutos, seconds=indice),
            )
        )
    sessao.flush()


def test_lotes_vem_do_mais_recente_com_apostas_em_ordem_e_truncados(sessao):
    _lote(sessao, 900_001, 3, minutos=0)
    _lote(sessao, 900_002, MAX_RECENT_BETS_PER_GENERATION + 5, minutos=10)
    _lote(sessao, 900_003, 1, minutos=20)

    geracoes = list_recent_generations_with_bets()

    assert [g["generation_id"] for g in geracoes] == [900_003, 900_002, 900_001]
    por_id = {g["generation_id"]: g for g in geracoes}

    grande = por_id[900_002]
    assert grande["bet_count"] == MAX_RECENT_BETS_PER_GENERATION + 5
    assert grande["bets_truncated"] is True
    assert len(grande["bets"]) == MAX_RECENT_BETS_PER_GENERATION
    ids = [aposta.id for aposta in grande["bets"]]
    assert ids == sorted(ids)
    assert all(aposta.generation_id == 900_002 for aposta in grande["bets"])

    for generation_id, tamanho in ((900_001, 3), (900_003, 1)):
        assert por_id[generation_id]["bets_truncated"] is False
        assert len(por_id[generation_id]["bets"]) == tamanho


def test_historico_usa_duas_consultas_qualquer_que_seja_o_numero_de_lotes(sessao):
    for deslocamento in range(8):
        _lote(sessao, 910_000 + deslocamento, 2, minutos=deslocamento)

    consultas: list[str] = []

    def contar(_conn, _cursor, statement, *_args):
        consultas.append(statement)

    engine = sessao.get_bind()
    event.listen(engine, "before_cursor_execute", contar)
    try:
        geracoes = list_recent_generations_with_bets()
    finally:
        event.remove(engine, "before_cursor_execute", contar)

    assert len(geracoes) == 8
    assert len(consultas) == 2

