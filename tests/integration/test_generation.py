from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from app import db
from app.bets.combinatorics import (
    build_combination_report,
    calculate_individual_filter_targets,
    count_draws_matching_filters,
    count_possible_draw_combinations,
)
from app.bets.service import (
    generate_closure_bets,
    list_recent_generations,
    list_recent_generations_with_bets,
    save_generated_bets,
)
from app.core.numbers import (
    draw_parameters,
)
from app.models import Config, Draw
from tests.support import csrf_form_data, make_app


def test_filters_on_large_bets_cover_every_internal_six_number_draw() -> None:
    from app.bets.service import _passes_generation_filters

    numbers = [1, 2, 3, 4, 5, 6, 17]

    assert _passes_generation_filters(numbers, {"even_min": 2}) is True
    assert _passes_generation_filters(numbers, {"even_min": 3}) is False
    assert _passes_generation_filters(numbers, {"sum_min": 21, "sum_max": 37}) is True
    assert _passes_generation_filters(numbers, {"sum_max": 36}) is False
    assert _passes_generation_filters(numbers, {"consecutive_count": 5}) is False
    assert _passes_generation_filters(numbers, {"range_min_occupied": 2}) is False
    assert _passes_generation_filters(numbers, {"range_max_per_band": 5}) is False


def test_combination_report_counts_remaining_combinations_and_chance() -> None:
    report = build_combination_report(
        quantity=7, filters={"even_min": 2, "even_max": 4}
    )

    assert report["total"] == 50_063_860
    assert report["remaining"] == 40_325_950
    assert report["covered_combinations"] == 7
    assert report["steps"][0]["eliminated"] == 9_737_910
    assert count_possible_draw_combinations(even_min=7) == 0
    assert count_possible_draw_combinations(range_min_occupied=6) == 1_000_000
    assert count_possible_draw_combinations(range_max_per_band=1) == 1_000_000


def test_generate_closure_bets_builds_all_six_number_combinations() -> None:
    bets = generate_closure_bets([1, 2, 3, 4, 5, 6, 7])

    assert len(bets) == 7
    assert bets[0].numbers_csv == "1,2,3,4,5,6"
    assert bets[-1].numbers_csv == "2,3,4,5,6,7"


def test_count_draws_matching_sum_interval_filter() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
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
                    **draw_parameters([10, 11, 20, 30, 40, 50]),
                ),
                Draw(
                    contest=3,
                    n1=5,
                    n2=6,
                    n3=7,
                    n4=8,
                    n5=9,
                    n6=10,
                    **draw_parameters([5, 6, 7, 8, 9, 10]),
                ),
                Draw(
                    contest=4,
                    n1=10,
                    n2=20,
                    n3=30,
                    n4=40,
                    n5=50,
                    n6=60,
                    **draw_parameters([10, 20, 30, 40, 50, 60]),
                ),
            ]
        )
        db.session.commit()

        assert count_draws_matching_filters(sum_min=20, sum_max=50) == 2
        assert count_draws_matching_filters(sum_min=100, sum_max=150) == 0
        assert (
            count_draws_matching_filters(even_min=3, even_max=4, sum_min=40, sum_max=50)
            == 1
        )
        assert count_draws_matching_filters(consecutive_count=3) == 2
        assert count_draws_matching_filters(range_min_occupied=5) == 2
        assert count_draws_matching_filters(range_max_per_band=1) == 1


def test_bets_shows_draws_matching_current_filter_params() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
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
                    **draw_parameters([1, 2, 3, 4, 5, 6]),
                ),
                Draw(
                    contest=2,
                    n1=1,
                    n2=3,
                    n3=5,
                    n4=7,
                    n5=9,
                    n6=11,
                    **draw_parameters([1, 3, 5, 7, 9, 11]),
                ),
                Draw(
                    contest=3,
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
    response = client.get("/bets?even_min=3&even_max=3")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Concursos no BD que passariam" in text
    assert "Percentual de jogos que passariam" in text
    assert 'data-filter-preview-count value="1"' in text
    assert 'data-filter-preview-percent value="33,33%"' in text

    response = client.get("/api/draw-filter-preview?even_min=3&even_max=3")
    data = response.get_json()

    assert response.status_code == 200
    assert data["count"] == 1
    assert data["total"] == 3
    assert data["percentage"] == 33.33
    assert data["percentage_text"] == "33,33%"


def test_filter_targets_api_calculates_individual_thresholds() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
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
                    **draw_parameters([1, 2, 3, 4, 5, 6]),
                ),
                Draw(
                    contest=2,
                    n1=1,
                    n2=3,
                    n3=5,
                    n4=7,
                    n5=9,
                    n6=11,
                    **draw_parameters([1, 3, 5, 7, 9, 11]),
                ),
                Draw(
                    contest=3,
                    n1=10,
                    n2=11,
                    n3=20,
                    n4=30,
                    n5=40,
                    n6=50,
                    **draw_parameters([10, 11, 20, 30, 40, 50]),
                ),
                Draw(
                    contest=4,
                    n1=10,
                    n2=20,
                    n3=30,
                    n4=40,
                    n5=50,
                    n6=60,
                    **draw_parameters([10, 20, 30, 40, 50, 60]),
                ),
            ]
        )
        db.session.commit()

        targets = calculate_individual_filter_targets(75)

    assert targets["target_count"] == 3
    assert targets["parameters"]["consecutive_count"]["value"] == 2
    assert targets["parameters"]["even_min"]["value"] == 3
    assert targets["parameters"]["even_max"]["value"] == 5
    assert targets["parameters"]["sum_min"]["value"] == 36
    assert targets["parameters"]["sum_max"]["value"] == 161

    response = app.test_client().get("/api/filter-targets?target_percentage=75")
    data = response.get_json()

    assert response.status_code == 200
    assert data["total"] == 4
    assert data["parameters"]["consecutive_count"]["percentage_text"] == "75,00%"
    assert data["parameters"]["sum_max"]["value"] == 161


def test_contests_menu_item_opens_unfiltered_list_after_filtered_tab() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
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
    filtered_text = client.get("/contests?even_count=5").get_data(as_text=True)
    assert "Filtro ativo:" in filtered_text
    assert "pares = 5" in filtered_text

    dashboard_text = client.get("/dashboard").get_data(as_text=True)
    nav_start = dashboard_text.index('id="primary-nav"')
    contests_link_text = ">Concursos</a>"
    contests_link_end = dashboard_text.index(contests_link_text, nav_start)
    href_start = dashboard_text.rfind('href="', nav_start, contests_link_end) + len(
        'href="'
    )
    href_end = dashboard_text.index('"', href_start)
    contests_menu_href = dashboard_text[href_start:href_end]

    response = client.get(contests_menu_href)
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert contests_menu_href == "/contests"
    assert "Filtro ativo:" not in text
    assert "3 concursos importados." in text
    assert "101" in text
    assert "202" in text
    assert "303" in text


def test_combinations_api_updates_from_generation_form_filters() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().get(
        "/api/combinations?quantity=7&even_min=2&even_max=4"
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data["total"] == 50_063_860
    assert data["remaining"] == 40_325_950
    assert data["covered_combinations"] == 7


def test_combinations_api_uses_closure_numbers_for_coverage() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().get(
        "/api/combinations?amount=3&quantity=6&closure_numbers=1+2+3+4+5+6+7"
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data["closure_mode"] is True
    assert data["closure_base_count"] == 7
    assert data["selected_amount"] == 7
    assert data["covered_by_amount"] == 7
    assert data["covered_by_amount_formatted"] == "7"


def test_combinations_api_closure_accepts_space_or_comma_separators() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    space_data = client.get(
        "/api/combinations",
        query_string={
            "amount": "3",
            "quantity": "6",
            "closure_numbers": "1 2 3 4 5 6 7 8 9 10",
        },
    ).get_json()
    comma_data = client.get(
        "/api/combinations",
        query_string={
            "amount": "3",
            "quantity": "6",
            "closure_numbers": "1,2,3,4,5,6,7,8,9,10",
        },
    ).get_json()

    assert space_data["closure_mode"] is True
    assert comma_data["closure_mode"] is True
    assert space_data["selected_amount"] == 210
    assert comma_data["selected_amount"] == 210
    assert space_data["covered_by_amount"] == 210
    assert comma_data["covered_by_amount"] == 210


def test_generation_url_is_authoritative_bookmarkable_and_can_be_cleared() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.get(
        "/rationale?amount=9&consecutive_count=3&even_min=2&even_max=4"
    )
    assert response.status_code == 200
    with client.session_transaction() as browser_session:
        assert "generation_params" not in browser_session

    response = client.get("/bets")
    text = response.get_data(as_text=True)
    assert 'name="amount" min="1" max="100" value="5"' in text
    assert 'name="even_min" min="0" max="6" placeholder="Opcional" value=""' in text

    state_url = "/bets?quantity=7&amount=9&consecutive_count=3&even_min=2&even_max=4"
    text = client.get(state_url).get_data(as_text=True)
    assert 'name="quantity" value="7"' in text
    assert 'name="amount" min="1" max="100" value="9"' in text
    assert (
        'name="consecutive_count" min="0" max="6" placeholder="Opcional" value="3"'
        in text
    )
    assert 'name="even_min" min="0" max="6" placeholder="Opcional" value="2"' in text
    assert 'name="even_max" min="0" max="6" placeholder="Opcional" value="4"' in text

    response = client.post(
        "/bets/clear",
        data=csrf_form_data(
            client,
            state_url,
            {
                "quantity": "7",
                "amount": "9",
                "consecutive_count": "3",
                "even_min": "2",
                "even_max": "4",
            },
        ),
        follow_redirects=False,
    )
    query = parse_qs(urlsplit(response.headers["Location"]).query)
    assert query == {"quantity": ["7"], "amount": ["9"]}

    response = client.get(response.headers["Location"])
    text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'name="amount" min="1" max="100" value="9"' in text
    assert (
        'name="consecutive_count" min="0" max="6" placeholder="Opcional" value=""'
        in text
    )
    assert 'name="even_min" min="0" max="6" placeholder="Opcional" value=""' in text


def test_generation_page_uses_url_without_browser_storage() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    first = client.get("/bets?quantity=6&amount=2&even_min=1").get_data(as_text=True)
    second = client.get("/bets?quantity=8&amount=4&sum_max=200").get_data(as_text=True)

    assert 'name="amount" min="1" max="100" value="2"' in first
    assert 'name="even_min" min="0" max="6" placeholder="Opcional" value="1"' in first
    assert 'name="quantity" value="8"' in second
    assert 'name="amount" min="1" max="100" value="4"' in second
    assert "localStorage" not in first
    assert 'src="/static/bets.js?v=' in first
    bets_js = Path("app/static/bets.js").read_text(encoding="utf-8")
    assert "history.replaceState" in bets_js
    assert "window.setTimeout(updatePreview, 200)" in bets_js
    assert "new AbortController()" in bets_js
    assert "previewController?.abort()" in bets_js
    assert "signal" in bets_js
    assert "localStorage" not in bets_js


def test_generation_sum_and_integer_inputs_are_bounded() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.get("/rationale?sum_min=999&sum_max=999")
    assert response.status_code == 200
    assert "sum_min=345" in response.get_data(as_text=True)
    assert "sum_max=345" in response.get_data(as_text=True)

    huge = "9" * 100
    response = client.get(f"/api/draw-filter-preview?sum_min={huge}")
    assert response.status_code == 200
    assert response.get_json()["count"] == 0


def test_clear_generation_filters_overrides_config_defaults() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.post(
        "/settings",
        data=csrf_form_data(
            client,
            "/settings",
            {
                "bet_quantity": "6",
                "generation_amount": "8",
                "consecutive_count": "3",
                "even_min": "2",
                "even_max": "4",
                "sum_min": "100",
                "sum_max": "220",
            },
        ),
        follow_redirects=True,
    )
    assert response.status_code == 200

    response = client.get("/bets")
    text = response.get_data(as_text=True)
    assert (
        'name="consecutive_count" min="0" max="6" placeholder="Opcional" value="3"'
        in text
    )
    assert 'name="even_min" min="0" max="6" placeholder="Opcional" value="2"' in text

    response = client.post(
        "/bets/clear", data=csrf_form_data(client, "/bets"), follow_redirects=True
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="amount" min="1" max="100" value="8"' in text
    assert (
        'name="consecutive_count" min="0" max="6" placeholder="Opcional" value=""'
        in text
    )
    assert 'name="even_min" min="0" max="6" placeholder="Opcional" value=""' in text
    assert 'name="even_max" min="0" max="6" placeholder="Opcional" value=""' in text
    assert 'name="sum_min" min="0" max="345" placeholder="Opcional" value=""' in text
    assert 'name="sum_max" min="0" max="345" placeholder="Opcional" value=""' in text


def test_saved_bets_are_grouped_by_generation() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

        first_saved, first_generation = save_generated_bets(
            6, ["1,2,3,4,5,6", "7,8,9,10,11,12"]
        )
        second_saved, second_generation = save_generated_bets(6, ["13,14,15,16,17,18"])
        generations = list_recent_generations()
        generations_with_bets = list_recent_generations_with_bets()

        assert first_saved == 2
        assert first_generation == 1
        assert second_saved == 1
        assert second_generation == 2
        assert [generation["generation_id"] for generation in generations] == [2, 1]
        assert generations[0]["bet_count"] == 1
        assert generations[1]["bet_count"] == 2
        assert "strategy" not in generations[0]
        assert len(generations_with_bets[1]["bets"]) == 2

    response = app.test_client().get("/bets")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Geração #1" in text
    assert "Apostas da geração #1" in text
    assert "data-generation-toggle" in text
    assert "data-generation-bets" in text
    assert "generation-bets-inline" in text
    assert "01" in text
    assert "12" in text


def test_saved_bets_are_deduplicated_and_have_a_hard_batch_limit(monkeypatch) -> None:
    import app.bets.service as betting_service

    app = make_app()
    with app.app_context():
        db.create_all()
        saved, generation_id = save_generated_bets(6, ["1,2,3,4,5,6", "6,5,4,3,2,1"])
        assert (saved, generation_id) == (1, 1)

        monkeypatch.setattr(betting_service, "MAX_SAVED_BETS", 2)
        with pytest.raises(RuntimeError, match="no máximo 2"):
            save_generated_bets(6, ["7,8,9,10,11,12"] * 3)


def test_persisted_generation_is_visible_as_a_group(monkeypatch) -> None:
    import app.bets.service as betting_service

    candidates = iter([[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]])
    monkeypatch.setattr(
        betting_service, "_secure_random_candidate", lambda _quantity: next(candidates)
    )
    app = make_app()
    with app.app_context():
        db.create_all()
        bets = betting_service.generate_bets(6, 2, persist=True)
        generations = list_recent_generations_with_bets()

        assert {bet.generation_id for bet in bets} == {1}
        assert len(generations) == 1
        assert generations[0]["generation_id"] == 1
        assert generations[0]["bet_count"] == 2


def test_bets_can_generate_mathematical_closure_from_base_numbers() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.post(
        "/bets",
        data=csrf_form_data(
            client,
            "/bets",
            {
                "action": "closure",
                "quantity": "6",
                "amount": "5",
                "closure_numbers": "1 2 3 4 5 6 7",
            },
        ),
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "7 apostas geradas pelo fechamento matemático." in text
    assert "01" in text
    assert "07" in text
    assert 'name="bet" value="1,2,3,4,5,6"' in text
    assert 'name="bet" value="2,3,4,5,6,7"' in text


def test_closure_bets_can_be_saved_when_default_quantity_is_greater_than_six() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add(Config(key="bet_quantity", value="7"))
        db.session.commit()

    client = app.test_client()
    payload = csrf_form_data(
        client,
        "/bets",
        {
            "action": "save",
            "quantity": "6",
            "bet": ["1,2,3,4,5,6", "2,3,4,5,6,7"],
        },
    )
    response = client.post("/bets", data=payload, follow_redirects=True)

    assert response.status_code == 200
    assert "2 apostas gravadas" in response.get_data(as_text=True)
    with app.app_context():
        from app.models import GeneratedBet

        assert GeneratedBet.query.count() == 2
        assert {bet.quantity for bet in GeneratedBet.query.all()} == {6}


def test_bets_summary_uses_closure_labels_when_closure_numbers_are_present() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().get(
        "/bets?amount=3&quantity=6&closure_numbers=1+2+3+4+5+6+7"
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Apostas no fechamento" in text
    assert "Chance no fechamento" in text


def test_rationale_uses_closure_numbers_and_preserves_field_on_return() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().get(
        "/rationale?amount=3&quantity=6&even_min=2&closure_numbers=1+2+3+4+5+6+7"
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Resumo dos filtros" not in text
    assert "Quantidade de apostas = C(7, 6) = 7" in text
    assert "Nesse modo, os filtros da aba de geração ficam opcionais" in text
    assert "amount=3" in text
    assert "closure_numbers=1+2+3+4+5+6+7" in text
