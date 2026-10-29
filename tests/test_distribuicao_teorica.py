"""Oráculos matemáticos independentes da DP de distribuição conjunta."""

import math
from collections import Counter
from itertools import combinations

import pytest

from app.bets.combinatorics import (
    TOTAL_DRAW_COMBINATIONS,
    _combination_distribution,
    build_combination_report,
    count_possible_draw_combinations,
)


def test_massa_total_e_soma_esperada_preservam_universo_combinatorio():
    distribuicao = _combination_distribution()
    assert sum(distribuicao.values()) == math.comb(60, 6) == TOTAL_DRAW_COMBINATIONS
    assert sum(chave[2] * qtd for chave, qtd in distribuicao.items()) == TOTAL_DRAW_COMBINATIONS * 183


@pytest.mark.parametrize("pares", range(7))
def test_marginal_de_pares_corresponde_a_hipergeometrica(pares):
    assert count_possible_draw_combinations(even_min=pares, even_max=pares) == math.comb(30, pares) * math.comb(30, 6 - pares)


def test_sem_adjacentes_um_por_faixa_e_bloco_de_seis():
    assert count_possible_draw_combinations(consecutive_count=0) == math.comb(55, 6)
    assert count_possible_draw_combinations(range_max_per_band=1) == 10 ** 6
    assert count_possible_draw_combinations(range_min_occupied=6) == 10 ** 6
    assert TOTAL_DRAW_COMBINATIONS - count_possible_draw_combinations(consecutive_count=5) == 55


def test_filtros_conjuntos_em_somas_baixas_batem_enumeracao_exaustiva():
    # Se a soma é <=30, a maior dezena é <=15 (as outras somam no mínimo15).
    # O oráculo percorre todos esses jogos, sem usar GenerationCriteria.
    esperado = Counter()
    for jogo in combinations(range(1, 16), 6):
        if sum(jogo) <= 30:
            esperado[(sum(jogo), sum(n % 2 == 0 for n in jogo))] += 1
    for (soma, pares), quantidade in esperado.items():
        assert count_possible_draw_combinations(sum_min=soma, sum_max=soma, even_min=pares, even_max=pares) == quantidade
    assert count_possible_draw_combinations(sum_max=20) == 0
    assert count_possible_draw_combinations(sum_min=346) == 0


def test_simetria_por_reflexao_dezenas_e_relatorio_cumulativo():
    for soma in (21, 22, 30, 100, 183):
        assert count_possible_draw_combinations(sum_min=soma, sum_max=soma) == count_possible_draw_combinations(sum_min=366 - soma, sum_max=366 - soma)
    filtros = {"even_min": 2, "even_max": 4, "sum_min": 100, "sum_max": 250,
               "range_min_occupied": 4, "range_max_per_band": 2, "consecutive_count": 2}
    relatorio = build_combination_report(8, filtros)
    assert relatorio["covered_combinations"] == math.comb(8, 6)
    anterior = TOTAL_DRAW_COMBINATIONS
    for etapa in relatorio["steps"]:
        assert etapa["previous_remaining"] == anterior
        assert 0 <= etapa["remaining"] <= anterior
        assert etapa["eliminated"] == anterior - etapa["remaining"]
        anterior = etapa["remaining"]
    assert anterior == relatorio["remaining"] == count_possible_draw_combinations(**filtros)
