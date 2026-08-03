from __future__ import annotations

from app import db
from app.core.numbers import (
    draw_parameters,
)
from app.models import Draw
from tests.support import make_app


def test_contests_filters_by_dashboard_history_parameters() -> None:
    app = make_app()
    with app.app_context():
        db.session.add_all(
            [
                Draw(
                    contest=101,
                    n1=1,
                    n2=2,
                    n3=3,
                    n4=4,
                    n5=5,
                    n6=6,
                    **draw_parameters([1, 2, 3, 4, 5, 6]),
                ),
                Draw(
                    contest=202,
                    n1=1,
                    n2=3,
                    n3=5,
                    n4=7,
                    n5=9,
                    n6=11,
                    **draw_parameters([1, 3, 5, 7, 9, 11]),
                ),
                Draw(
                    contest=303,
                    n1=10,
                    n2=11,
                    n3=20,
                    n4=30,
                    n5=40,
                    n6=50,
                    **draw_parameters([10, 11, 20, 30, 40, 50]),
                ),
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


def test_dashboard_history_filter_link_applies_filter_when_followed_from_other_tab() -> (
    None
):
    app = make_app()
    with app.app_context():
        db.session.add_all(
            [
                Draw(
                    contest=101,
                    n1=1,
                    n2=2,
                    n3=3,
                    n4=4,
                    n5=5,
                    n6=6,
                    **draw_parameters([1, 2, 3, 4, 5, 6]),
                ),
                Draw(
                    contest=202,
                    n1=1,
                    n2=3,
                    n3=5,
                    n4=7,
                    n5=9,
                    n6=11,
                    **draw_parameters([1, 3, 5, 7, 9, 11]),
                ),
                Draw(
                    contest=303,
                    n1=10,
                    n2=11,
                    n3=20,
                    n4=30,
                    n5=40,
                    n6=50,
                    **draw_parameters([10, 11, 20, 30, 40, 50]),
                ),
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


def test_bets_form_submits_generation_filters_to_rationale() -> None:
    app = make_app()
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
    assert 'name="closure_numbers"' in text
    assert 'formmethod="get"' in text
    assert 'formaction="/rationale"' in text

    response = app.test_client().get(
        "/rationale?amount=8&quantity=6&consecutive_count=3&even_min=2&even_max=4&sum_min=100&sum_max=250&range_min_occupied=4&range_max_per_band=2"
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "amount=8" in text
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


def test_contests_page_summarizes_filtered_results() -> None:
    app = make_app()
    with app.app_context():
        db.session.add_all(
            [
                Draw(
                    contest=1,
                    n1=1,
                    n2=2,
                    n3=3,
                    n4=4,
                    n5=5,
                    n6=6,
                    winners_6=1,
                    **draw_parameters([1, 2, 3, 4, 5, 6]),
                ),
                Draw(
                    contest=2,
                    n1=10,
                    n2=11,
                    n3=20,
                    n4=30,
                    n5=40,
                    n6=50,
                    winners_6=0,
                    **draw_parameters([10, 11, 20, 30, 40, 50]),
                ),
            ]
        )
        db.session.commit()

    response = app.test_client().get("/contests")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "2 concursos importados." in text

    response = app.test_client().get("/contests?even_count=3&winners_only=1")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "1 concurso com acertadores na Mega Sena encontrado." in text


def test_dashboard_renders_statistical_sections() -> None:
    app = make_app()
    response = app.test_client().get("/dashboard")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Frequência X Número Sorteado" in text
    assert "Frequência x Soma dos Números Sorteados" in text
    assert "Distribuição por faixas" in text
    assert "frequency-sequence" in text
    assert 'id="freq-chart"' in text
    assert 'id="sum-histogram"' in text


def test_dashboard_renders_period_selector_buttons() -> None:
    """A página do dashboard deve exibir os botões de seleção de período."""
    app = make_app()
    with app.app_context():
        db.session.add(
            Draw(
                contest=1,
                n1=1,
                n2=2,
                n3=3,
                n4=4,
                n5=5,
                n6=6,
                **draw_parameters([1, 2, 3, 4, 5, 6]),
            )
        )
        db.session.commit()

    response = app.test_client().get("/dashboard")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-period="500"' in text
    assert 'data-period="200"' in text
    assert 'data-period="100"' in text
    assert 'id="freq-chart"' in text
    assert 'hx-target="#dashboard-content"' in text
    assert 'src="/static/vendor/htmx-2.0.10.min.js?v=' in text


def test_dashboard_stats_endpoint_returns_full_payload_for_all_sections() -> None:
    """GET /api/dashboard-stats deve retornar todos os campos usados pelo dashboard."""
    app = make_app()
    with app.app_context():
        for contest in range(1, 21):
            db.session.add(
                Draw(
                    contest=contest,
                    n1=1,
                    n2=2,
                    n3=3,
                    n4=4,
                    n5=5,
                    n6=6,
                    **draw_parameters([1, 2, 3, 4, 5, 6]),
                )
            )
        db.session.commit()

    response = app.test_client().get("/api/dashboard-stats?count=10")
    data = response.get_json()

    assert response.status_code == 200
    expected_keys = {
        "count",
        "actual_count",
        "total_draws",
        "mega_sena_games_with_winners",
        "mega_sena_games_without_winners",
        "mega_sena_games_with_winners_pct",
        "mega_sena_games_without_winners_pct",
        "prize_cards",
        "even_distribution",
        "consecutive_distribution",
        "ranges",
        "most_frequent",
        "least_frequent",
        "frequency",
        "sum_histogram",
    }
    assert expected_keys.issubset(data.keys())
    assert data["count"] == 10
    assert data["actual_count"] == 10
    assert data["total_draws"] == 10


def test_dashboard_stats_endpoint_default_considers_all_draws() -> None:
    """GET /api/dashboard-stats sem `count` deve considerar todo o histórico."""
    app = make_app()
    with app.app_context():
        for contest in range(1, 8):
            db.session.add(
                Draw(
                    contest=contest,
                    n1=1,
                    n2=2,
                    n3=3,
                    n4=4,
                    n5=5,
                    n6=6,
                    **draw_parameters([1, 2, 3, 4, 5, 6]),
                )
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
        for contest in range(1, 4):
            db.session.add(
                Draw(
                    contest=contest,
                    n1=1,
                    n2=2,
                    n3=3,
                    n4=4,
                    n5=5,
                    n6=6,
                    **draw_parameters([1, 2, 3, 4, 5, 6]),
                )
            )
        db.session.commit()

    response = app.test_client().get("/api/dashboard-stats?count=1")
    data = response.get_json()

    assert response.status_code == 200
    assert data["total_draws"] == 3
