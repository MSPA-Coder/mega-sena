from __future__ import annotations

from io import BytesIO  # noqa: F401
from pathlib import Path  # noqa: F401
from zipfile import ZIP_DEFLATED, ZipFile  # noqa: F401

import pytest  # noqa: F401

from app import create_app, db  # noqa: F401
from app.models import Config, Draw  # noqa: F401
from app.bets.combinatorics import (  # noqa: F401
    build_combination_report,
    calculate_individual_filter_targets,
    count_draws_matching_filters,
    count_possible_draw_combinations,
)
from app.bets.service import (  # noqa: F401
    generate_closure_bets,
    list_recent_generations,
    list_recent_generations_with_bets,
    save_generated_bets,
)
from app.core.numbers import (  # noqa: F401
    count_consecutive_numbers,
    count_even_numbers,
    count_occupied_range_bands,
    draw_parameters,
    max_range_band_count,
)
from app.draws.importing import import_results_from_xlsx  # noqa: F401
from app.draws.statistics import (  # noqa: F401
    build_recent_frequency,
    build_stats,
    ensure_draw_parameters_current,
)
from app.settings.service import get_config_values  # noqa: F401
from tests.support import csrf_form_data, css_source, make_app, workbook_bytes  # noqa: F401


def test_contests_filters_by_dashboard_history_parameters() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Draw(contest=101, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6])),
                Draw(contest=202, n1=1, n2=3, n3=5, n4=7, n5=9, n6=11, **draw_parameters([1, 3, 5, 7, 9, 11])),
                Draw(contest=303, n1=10, n2=11, n3=20, n4=30, n5=40, n6=50, **draw_parameters([10, 11, 20, 30, 40, 50])),
            ]
        )
        db.session.commit()

    response = app.test_client().get("/contests?consecutive_count=6")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Filtro ativo: maior sequência de números consecutivos = 6" in text
    assert "<td>101</td>" in text
    assert "<td>202</td>" not in text
    assert "<td>303</td>" not in text

    response = app.test_client().get("/contests?consecutive_count=0")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Filtro ativo: maior sequência de números consecutivos = 0" in text
    assert "<td>202</td>" in text
    assert "<td>101</td>" not in text
    assert "<td>303</td>" not in text

    response = app.test_client().get("/contests?even_count=5")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Filtro ativo: quantidade de números pares = 5" in text
    assert "303" in text
    assert "101" not in text
    assert "202" not in text


def test_dashboard_history_filter_link_applies_filter_when_followed_from_other_tab() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Draw(contest=101, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6])),
                Draw(contest=202, n1=1, n2=3, n3=5, n4=7, n5=9, n6=11, **draw_parameters([1, 3, 5, 7, 9, 11])),
                Draw(contest=303, n1=10, n2=11, n3=20, n4=30, n5=40, n6=50, **draw_parameters([10, 11, 20, 30, 40, 50])),
            ]
        )
        db.session.commit()

    client = app.test_client()
    dashboard_text = client.get("/dashboard").get_data(as_text=True)
    href_marker = 'href="/contests?even_count=5"'
    href_start = dashboard_text.index(href_marker) + len('href="')
    href_end = dashboard_text.index('"', href_start)
    filter_href = dashboard_text[href_start:href_end]

    response = client.get(filter_href)
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert filter_href == "/contests?even_count=5"
    assert "Filtro ativo:" in text
    assert "pares = 5" in text
    assert "303" in text
    assert "101" not in text
    assert "202" not in text


def test_rationale_button_submits_even_range_filters_with_get() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().get("/bets")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="even_min"' in text
    assert 'name="even_max"' in text
    assert 'name="consecutive_count" min="0" max="6"' in text
    assert 'name="even_min" min="0" max="6"' in text
    assert 'name="even_max" min="0" max="6"' in text
    assert 'name="range_min_occupied" min="1" max="6"' in text
    assert 'name="range_max_per_band" min="1" max="6"' in text
    assert 'name="amount"' in text
    assert 'type="hidden" name="quantity" value="6"' in text
    assert "Cada aposta usa sempre 6 numeros." not in text
    assert "Parâmetros para a Geração das Apostas" in text
    assert "8. Fechamentos matemáticos" not in text
    assert "Dezenas do fechamento" in text
    assert "Distribuição por faixas" not in text
    assert "10 dezenas geram C(10, 6) = 210 apostas." not in text
    assert "As apostas são geradas com gerador aleatório seguro do Python e validadas contra os filtros informados." in text
    assert "Fluxo aplicado" in text
    assert "Os parâmetros abaixo restringem a geração" not in text
    assert text.index("As apostas são geradas com gerador aleatório seguro") < text.index("Fluxo aplicado")
    assert 'formmethod="get"' in text
    assert 'formaction="/rationale"' in text
    assert text.index("data-filter-target-button") < text.index(">Racional<") < text.index("Limpar filtros") < text.index(">Gerar Apostas<")

    response = app.test_client().get("/rationale?amount=8&quantity=6&consecutive_count=3&even_min=2&even_max=4&sum_min=100&sum_max=250&range_min_occupied=4&range_max_per_band=2")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "amount=8" in text
    assert "strategy=" not in text
    assert "method=" not in text
    assert "consecutive_count=3" in text
    assert "even_min=2" in text
    assert "even_max=4" in text
    assert "sum_min=100" in text
    assert "sum_max=250" in text
    assert "range_min_occupied=4" in text
    assert "range_max_per_band=2" in text
    assert "Maior sequência de números consecutivos = até 3" in text
    assert "maior_sequencia_consecutiva(jogo) &lt;= 3" in text
    assert "Quantidade de números pares = 2 a 4" in text
    assert "Soma dos números = 100 a 250" in text
    assert "Distribuição por faixas = mín. 4 faixas, máx. 2 por faixa" in text
    assert "Nenhum filtro aplicado" not in text
    assert "Resumo dos filtros" not in text
    rationale_text = text[text.index("Racional da aposta e dos filtros"):text.index("Leitura correta")]
    assert rationale_text.index("Quantidade de números pares = 2 a 4") < rationale_text.index("Soma dos números = 100 a 250")
    assert rationale_text.index("Soma dos números = 100 a 250") < rationale_text.index("Distribuição por faixas = mín. 4 faixas, máx. 2 por faixa")
    assert rationale_text.index("Distribuição por faixas = mín. 4 faixas, máx. 2 por faixa") < rationale_text.index("Maior sequência de números consecutivos = até 3")


def test_contests_header_does_not_show_clear_filter_button() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Draw(contest=1, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, winners_6=1, **draw_parameters([1, 2, 3, 4, 5, 6])),
                Draw(contest=2, n1=10, n2=11, n3=20, n4=30, n5=40, n6=50, winners_6=0, **draw_parameters([10, 11, 20, 30, 40, 50])),
            ]
        )
        db.session.commit()

    response = app.test_client().get("/contests")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "2 concursos importados." in text
    assert "Lista de concursos importados." not in text

    response = app.test_client().get("/contests?even_count=3&winners_only=1")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "contests-header" in text
    assert "1 concurso com acertadores na Mega Sena encontrado." in text
    assert "Limpar filtro" not in text


def test_dashboard_chart_titles_and_frequency_cards() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().get("/dashboard")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Frequência X Número Sorteado" in text
    assert "Frequência x Soma dos Números Sorteados" in text
    assert "Distribuição por faixas" in text
    assert "Divide as dezenas em blocos" not in text
    assert "frequency-y-axis-title" not in text
    assert "frequency-x-axis-title" not in text
    assert "sum-y-axis-title" not in text
    assert "sum-x-axis-title" not in text
    assert "frequency-sequence" in text
    assert "chart-panel" in text
    assert "dashboard-chart-panel" in text
    assert text.index("Quantidade de números pares") < text.index("Maior sequência consecutiva")
    assert text.index("Maior sequência consecutiva") < text.index("Distribuição por faixas")
    assert text.index("Distribuição por faixas") < text.index("Mais frequentes")
    assert text.index("Mais frequentes") < text.index("Frequência x Soma dos Números Sorteados")
    assert text.index("Mais frequentes") < text.index("Frequência X Número Sorteado")


def test_build_recent_frequency_with_no_draws_returns_zeroed_payload() -> None:
    """Sem concursos, build_recent_frequency deve retornar estrutura zerada, sem erro."""
    app = make_app()
    with app.app_context():
        db.create_all()
        result = build_recent_frequency(None)

    assert result["actual_count"] == 0
    assert result["max_frequency"] == 0
    assert result["most_frequent"] == []
    assert all(v == 0 for v in result["frequency"].values())
    assert len(result["frequency"]) == 60


def test_build_recent_frequency_all_draws_counts_every_number() -> None:
    """Sem limite de período, deve considerar todos os concursos cadastrados."""
    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Draw(contest=1, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6])),
                Draw(contest=2, n1=1, n2=2, n3=3, n4=10, n5=20, n6=30, **draw_parameters([1, 2, 3, 10, 20, 30])),
            ]
        )
        db.session.commit()

        result = build_recent_frequency(None)

    assert result["count"] is None
    assert result["actual_count"] == 2
    assert result["frequency"]["1"] == 2
    assert result["frequency"]["2"] == 2
    assert result["frequency"]["3"] == 2
    assert result["frequency"]["4"] == 1
    assert result["frequency"]["30"] == 1
    assert result["max_frequency"] == 2


def test_build_recent_frequency_respects_period_limit() -> None:
    """Com `count` informado, apenas os concursos mais recentes (maior número) entram no cálculo."""
    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Draw(contest=1, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6])),
                Draw(contest=2, n1=7, n2=8, n3=9, n4=10, n5=11, n6=12, **draw_parameters([7, 8, 9, 10, 11, 12])),
                Draw(contest=3, n1=13, n2=14, n3=15, n4=16, n5=17, n6=18, **draw_parameters([13, 14, 15, 16, 17, 18])),
            ]
        )
        db.session.commit()

        result = build_recent_frequency(1)

    # Apenas o concurso 3 (o mais recente) deve ser considerado.
    assert result["actual_count"] == 1
    assert result["frequency"]["13"] == 1
    assert result["frequency"]["1"] == 0
    assert result["frequency"]["7"] == 0


def test_recent_frequency_endpoint_returns_json_with_all_draws_by_default() -> None:
    """GET /api/recent-frequency sem parâmetro deve considerar todos os concursos."""
    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Draw(contest=1, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6])),
                Draw(contest=2, n1=10, n2=11, n3=20, n4=30, n5=40, n6=50, **draw_parameters([10, 11, 20, 30, 40, 50])),
            ]
        )
        db.session.commit()

    response = app.test_client().get("/api/recent-frequency")
    data = response.get_json()

    assert response.status_code == 200
    assert data["count"] is None
    assert data["actual_count"] == 2
    assert sum(data["frequency"].values()) == 12  # 2 concursos x 6 números


def test_recent_frequency_endpoint_filters_by_count_param() -> None:
    """GET /api/recent-frequency?count=N deve limitar aos N concursos mais recentes."""
    app = make_app()
    with app.app_context():
        db.create_all()
        for contest in range(1, 21):
            nums = [contest, contest + 1, contest + 2, contest + 3, contest + 4, contest + 5]
            nums = [min(n, 60) for n in nums]
            db.session.add(
                Draw(contest=contest, n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5], **draw_parameters(sorted(set(nums)) if len(set(nums)) == 6 else [1, 2, 3, 4, 5, 6]))
            )
        db.session.commit()

    # count=15 está dentro do intervalo permitido (10-10000) e abaixo do total (20),
    # então deve ser respeitado exatamente.
    response = app.test_client().get("/api/recent-frequency?count=15")
    data = response.get_json()

    assert response.status_code == 200
    assert data["count"] == 15
    assert data["actual_count"] == 15


def test_recent_frequency_endpoint_clamps_out_of_range_count() -> None:
    """Valores de `count` fora do intervalo permitido (10-10000) devem ser ajustados, sem erro 400."""
    app = make_app()
    with app.app_context():
        db.create_all()
        for contest in range(1, 4):
            db.session.add(
                Draw(contest=contest, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6]))
            )
        db.session.commit()

    # count=1 deve ser elevado ao mínimo de 10, mas como só há 3 concursos no banco,
    # o resultado real fica limitado pelo total existente.
    response = app.test_client().get("/api/recent-frequency?count=1")
    data = response.get_json()

    assert response.status_code == 200
    assert data["actual_count"] == 3


def test_recent_frequency_endpoint_ignores_invalid_count_value() -> None:
    """Um valor não numérico em `count` deve ser ignorado, retornando todos os concursos."""
    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add(Draw(contest=1, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6])))
        db.session.commit()

    response = app.test_client().get("/api/recent-frequency?count=abc")
    data = response.get_json()

    assert response.status_code == 200
    assert data["count"] is None
    assert data["actual_count"] == 1


def test_dashboard_renders_period_selector_buttons() -> None:
    """A página do dashboard deve exibir os botões de seleção de período."""
    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add(Draw(contest=1, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6])))
        db.session.commit()

    response = app.test_client().get("/dashboard")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-period="500"' in text
    assert 'data-period="200"' in text
    assert 'data-period="100"' in text
    assert 'id="freq-chart"' in text
    assert "/api/dashboard-stats" in text
    assert 'src="/static/dashboard.js?v=' in text
    dashboard_js = Path("app/static/dashboard.js").read_text(encoding="utf-8")
    assert "new AbortController()" in dashboard_js
    assert "dashboardController.abort()" in dashboard_js


def test_dashboard_has_three_cards_in_top_row_matching_grid_widths() -> None:
    """
    A seção .cards deve ter 3 cards (Concursos, Acertadores, Período),
    usando a mesma proporção de colunas de .dashboard-top-grid, para que
    cada um se alinhe em largura com o card correspondente na linha abaixo.
    """
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().get("/dashboard")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="dash-concursos-card"' in text
    assert 'id="dash-acertadores-card"' in text
    assert 'id="dash-period-card"' in text
    # As 3 seções devem aparecer antes de "Quantidade de números pares",
    # ou seja, dentro da seção .cards.
    cards_idx = text.index('<section class="cards">')
    grid_idx = text.index("Quantidade de números pares")
    assert cards_idx < text.index('id="dash-period-card"') < grid_idx


def test_period_card_contains_buttons_moved_from_chart_panel() -> None:
    """Os botões de período devem estar dentro do novo card, não mais no painel do gráfico."""
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().get("/dashboard")
    text = response.get_data(as_text=True)

    period_card_start = text.index('id="dash-period-card"')
    period_card_end = text.index("</div>", text.index("freq-period-label"))
    period_card_html = text[period_card_start:period_card_end]

    assert 'data-period="500"' in period_card_html
    assert 'data-period="200"' in period_card_html
    assert 'data-period="100"' in period_card_html
    assert "freq-chart-header" not in text  # wrapper antigo não existe mais


def test_css_cards_grid_matches_dashboard_top_grid_proportions() -> None:
    """O CSS de .cards deve usar a mesma proporção 0.9fr/1fr/1.35fr de .dashboard-top-grid."""
    css = css_source()

    assert "minmax(0, .9fr) minmax(0, 1fr) minmax(0, 1.35fr)" in css
    # A regra antiga de 4 colunas iguais não deve mais existir para .cards.
    cards_rule_start = css.index(".cards {")
    cards_rule_end = css.index("}", cards_rule_start)
    cards_rule = css[cards_rule_start:cards_rule_end]
    assert "repeat(4, 1fr)" not in cards_rule


def test_dashboard_stats_endpoint_returns_full_payload_for_all_sections() -> None:
    """GET /api/dashboard-stats deve retornar todos os campos usados pelo dashboard."""
    app = make_app()
    with app.app_context():
        db.create_all()
        for contest in range(1, 21):
            db.session.add(
                Draw(contest=contest, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6]))
            )
        db.session.commit()

    response = app.test_client().get("/api/dashboard-stats?count=10")
    data = response.get_json()

    assert response.status_code == 200
    expected_keys = {
        "count", "actual_count", "total_draws",
        "mega_sena_games_with_winners", "mega_sena_games_without_winners",
        "mega_sena_games_with_winners_pct", "mega_sena_games_without_winners_pct",
        "prize_cards", "even_distribution", "consecutive_distribution",
        "ranges", "most_frequent", "least_frequent", "frequency", "sum_histogram",
    }
    assert expected_keys.issubset(data.keys())
    assert data["count"] == 10
    assert data["actual_count"] == 10
    assert data["total_draws"] == 10


def test_dashboard_stats_endpoint_default_considers_all_draws() -> None:
    """GET /api/dashboard-stats sem `count` deve considerar todo o histórico."""
    app = make_app()
    with app.app_context():
        db.create_all()
        for contest in range(1, 8):
            db.session.add(
                Draw(contest=contest, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6]))
            )
        db.session.commit()

    response = app.test_client().get("/api/dashboard-stats")
    data = response.get_json()

    assert response.status_code == 200
    assert data["count"] is None
    assert data["total_draws"] == 7


def test_dashboard_stats_endpoint_clamps_out_of_range_count() -> None:
    """`count` fora do intervalo 10-10000 deve ser ajustado, sem erro 400."""
    app = make_app()
    with app.app_context():
        db.create_all()
        for contest in range(1, 4):
            db.session.add(
                Draw(contest=contest, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6]))
            )
        db.session.commit()

    response = app.test_client().get("/api/dashboard-stats?count=1")
    data = response.get_json()

    assert response.status_code == 200
    assert data["total_draws"] == 3
