"""Estatísticas e filtros devem refletir os concursos realmente persistidos."""

from datetime import date
from itertools import combinations

import pytest

from app.bets.combinatorics import (
    calculate_individual_filter_targets,
    count_distinct_internal_combinations,
    count_draws_matching_filters,
)
from app.draws.statistics import all_draw_numbers, build_stats
from app.models import Draw

pytestmark = pytest.mark.banco


@pytest.fixture
def historico(sessao):
    casos = [
        ([1, 2, 3, 4, 5, 6], 21, 3, 6, (0, 2, 5)),
        ([1, 3, 5, 7, 9, 11], 36, 0, 0, (1, 0, 8)),
        ([4, 11, 23, 35, 47, 52], 172, 2, 0, (2, 3, 0)),
    ]
    assert sessao.query(Draw).count() == 0
    for indice, (numeros, soma, pares, sequencia, premios) in enumerate(casos, start=1):
        sessao.add(Draw(
            contest=indice, draw_date=date(2026, 10, indice),
            **{f"n{i}": n for i, n in enumerate(numeros, start=1)},
            total_sum=soma, even_count=pares, consecutive_count=sequencia,
            winners_6=premios[0], winners_5=premios[1], winners_4=premios[2],
        ))
    sessao.flush()
    return [caso[0] for caso in casos]


def test_estatisticas_preservam_frequencias_e_diferenciam_ganhadores_de_concursos(historico):
    resultado = build_stats()
    assert resultado["total_draws"] == 3
    assert sum(resultado["frequency"].values()) == 18
    assert resultado["frequency"][1] == 2
    assert resultado["frequency"][60] == 0
    assert sum(resultado["ranges"].values()) == 18
    assert resultado["prize_cards"]["mega_sena"]["games"] == 2
    assert resultado["prize_cards"]["mega_sena"]["winners"] == 3
    assert resultado["prize_cards"]["quina"]["games"] == 2
    assert resultado["prize_cards"]["quina"]["winners"] == 5
    assert resultado["even_distribution"] == {0: 1, 2: 1, 3: 1}
    assert resultado["consecutive_distribution"] == {0: 2, 6: 1}
    assert sum(item["count"] for item in resultado["sum_histogram"]["bins"]) == 3
    assert all_draw_numbers() == historico


def test_janela_estatistica_considera_concurso_mais_recente(historico):
    resultado = build_stats(count=1)
    assert resultado["total_draws"] == 1
    assert {n for n, quantidade in resultado["frequency"].items() if quantidade} == set(historico[-1])
    assert resultado["prize_cards"]["mega_sena"]["winners"] == 2


@pytest.mark.parametrize(("filtros", "esperado"), [
    ({}, 3),
    ({"even_min": 2, "even_max": 2}, 1),
    ({"sum_min": 172, "sum_max": 172}, 1),
    ({"sum_max": 20}, 0),
    ({"consecutive_count": 0}, 2),
    ({"range_min_occupied": 6}, 1),
    ({"range_max_per_band": 1}, 1),
    ({"range_min_occupied": 2, "range_max_per_band": 5}, 2),
    ({"even_min": 3, "range_min_occupied": 2}, 0),
])
def test_filtros_contam_intersecao_e_incluem_limites(historico, filtros, esperado):
    assert count_draws_matching_filters(**filtros) == esperado


@pytest.mark.parametrize("alvo", [0, 50, 80, 100, float("nan"), "invalido"])
def test_faixas_sugeridas_cumprem_percentual_individual(historico, alvo):
    resultado = calculate_individual_filter_targets(alvo)
    percentual = alvo if isinstance(alvo, int) else 80
    assert resultado["total"] == 3
    assert resultado["target_percentage"] == percentual
    for chave, faixa in resultado["parameters"].items():
        quantidade = count_draws_matching_filters(**{chave: faixa["value"]})
        assert quantidade * 100 >= percentual * 3


def test_sem_historico_nao_inventa_estatistica_ou_faixas(sessao):
    resultado = build_stats()
    assert resultado["total_draws"] == 0
    assert resultado["mega_sena_games_with_winners_pct"] == 0
    assert resultado["sum_histogram"]["bins"] == []
    assert all(item["value"] is None for item in calculate_individual_filter_targets(80)["parameters"].values())


def test_cobertura_de_apostas_remove_sobreposicao_e_independe_da_ordem(sessao):
    apostas = [list(range(1, 8)), list(range(2, 9)), list(range(7, 0, -1)), [1, 2, 3]]
    esperado = set(combinations(range(1, 8), 6)) | set(combinations(range(2, 9), 6))
    assert len(esperado) == 13
    assert count_distinct_internal_combinations(apostas) == len(esperado)


def test_uniao_muito_grande_e_recusada_sem_estimativa_disfarcada(sessao):
    assert count_distinct_internal_combinations([range(1, 61)]) is None
