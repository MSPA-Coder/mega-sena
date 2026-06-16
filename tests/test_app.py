from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from flask import Flask
from openpyxl import Workbook

from app import db
from app.models import Config, Draw
from app.routes import bp
from app.services import build_combination_report, build_recent_frequency, calculate_individual_filter_targets, count_consecutive_numbers, count_draws_matching_filters, count_even_numbers, count_occupied_range_bands, count_possible_draw_combinations, draw_parameters, generate_closure_bets, get_config_values, import_results_from_xlsx, list_recent_generations, list_recent_generations_with_bets, max_range_band_count, save_generated_bets


def make_app() -> Flask:
    template_folder = Path(__file__).resolve().parents[1] / "app" / "templates"
    app = Flask(__name__, template_folder=str(template_folder))
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "test"
    app.jinja_env.filters["brl0"] = lambda cents: str(cents or "")
    db.init_app(app)
    app.register_blueprint(bp)
    return app


def workbook_bytes(rows: list[list[object]], bad_dimension: bool = False) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "Concurso",
            "Data do Sorteio",
            "Bola1",
            "Bola2",
            "Bola3",
            "Bola4",
            "Bola5",
            "Bola6",
            "Ganhadores 6 acertos",
            "Ganhadores 5 acertos",
            "Ganhadores 4 acertos",
            "Rateio 6 acertos",
            "Rateio 5 acertos",
            "Rateio 4 acertos",
            "Acumulado 6 acertos",
        ]
    )
    for row in rows:
        sheet.append(row)

    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    if not bad_dimension:
        return stream

    patched = BytesIO()
    with ZipFile(stream, "r") as source, ZipFile(patched, "w", ZIP_DEFLATED) as target:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                content = content.replace(b'<dimension ref="A1:O3"/>', b'<dimension ref="A1:O1"/>')
            target.writestr(info, content)
    patched.seek(0)
    return patched


def test_count_even_numbers_counts_only_even_dozen_values() -> None:
    assert count_even_numbers([1, 3, 5, 7, 9, 11]) == 0
    assert count_even_numbers([1, 2, 3, 4, 5, 6]) == 3
    assert count_even_numbers([10, 11, 20, 30, 40, 50]) == 5
    assert count_even_numbers([2, 4, 6, 8, 10, 12]) == 6


def test_count_consecutive_numbers_returns_longest_consecutive_sequence() -> None:
    assert count_consecutive_numbers([1, 3, 5, 7, 9, 11]) == 0
    assert count_consecutive_numbers([1, 2, 5, 10, 20, 30]) == 2
    assert count_consecutive_numbers([4, 10, 34, 35, 36, 50]) == 3
    assert count_consecutive_numbers([1, 2, 34, 35, 36, 50]) == 3
    assert count_consecutive_numbers([50, 51, 56, 57, 58, 59]) == 4


def test_range_band_metrics_count_occupied_bands_and_max_concentration() -> None:
    assert count_occupied_range_bands([1, 2, 3, 4, 5, 6]) == 1
    assert max_range_band_count([1, 2, 3, 4, 5, 6]) == 6
    assert count_occupied_range_bands([1, 12, 23, 34, 45, 56]) == 6
    assert max_range_band_count([1, 12, 23, 34, 45, 56]) == 1
    assert count_occupied_range_bands([1, 2, 12, 22, 32, 42]) == 5
    assert max_range_band_count([1, 2, 12, 22, 32, 42]) == 2


def test_combination_report_counts_remaining_combinations_and_chance() -> None:
    report = build_combination_report(quantity=7, filters={"even_min": 2, "even_max": 4})

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


def test_import_recalculates_bad_sheet_dimensions() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
        first = import_results_from_xlsx(
            workbook_bytes(
                [
                    [1, "01/01/2026", 1, 2, 3, 4, 5, 6, 0, 10, 100, "R$0,00", "R$1,00", "R$2,00", "R$3,00"],
                ]
            )
        )
        second = import_results_from_xlsx(
            workbook_bytes(
                [
                    [1, "01/01/2026", 1, 2, 3, 4, 5, 6, 0, 10, 100, "R$0,00", "R$1,00", "R$2,00", "R$3,00"],
                    [2, "02/01/2026", 7, 8, 9, 10, 11, 12, 1, 20, 200, "R$4,00", "R$5,00", "R$6,00", "R$7,00"],
                ],
                bad_dimension=True,
            )
        )

        assert first == {"imported": 1, "updated": 0, "ignored": 0}
        assert second == {"imported": 1, "updated": 0, "ignored": 1}
        assert Draw.query.count() == 2
        assert Draw.query.order_by(Draw.contest.desc()).first().contest == 2
        first_draw = Draw.query.filter_by(contest=1).one()
        assert first_draw.total_sum == 21
        assert first_draw.even_count == 3
        assert first_draw.consecutive_count == 6


def test_import_updates_existing_contest_when_stored_fields_change() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
        import_results_from_xlsx(
            workbook_bytes(
                [
                    [1, "01/01/2026", 1, 2, 3, 4, 5, 6, 0, 10, 100, "R$0,00", "R$1,00", "R$2,00", "R$3,00"],
                ]
            )
        )
        result = import_results_from_xlsx(
            workbook_bytes(
                [
                    [1, "01/01/2026", 1, 2, 3, 4, 5, 6, 1, 11, 101, "R$8,00", "R$9,00", "R$10,00", "R$11,00"],
                ]
            )
        )

        draw = Draw.query.filter_by(contest=1).one()
        assert result == {"imported": 0, "updated": 1, "ignored": 0}
        assert draw.winners_6 == 1
        assert draw.winners_5 == 11
        assert draw.prize_cents == 800


def test_count_draws_matching_sum_interval_filter() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add_all(
                [
                    Draw(contest=1, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6])),
                    Draw(contest=2, n1=10, n2=11, n3=20, n4=30, n5=40, n6=50, **draw_parameters([10, 11, 20, 30, 40, 50])),
                    Draw(contest=3, n1=5, n2=6, n3=7, n4=8, n5=9, n6=10, **draw_parameters([5, 6, 7, 8, 9, 10])),
                    Draw(contest=4, n1=10, n2=20, n3=30, n4=40, n5=50, n6=60, **draw_parameters([10, 20, 30, 40, 50, 60])),
                ]
            )
        db.session.commit()

        assert count_draws_matching_filters(sum_min=20, sum_max=50) == 2
        assert count_draws_matching_filters(sum_min=100, sum_max=150) == 0
        assert count_draws_matching_filters(even_min=3, even_max=4, sum_min=40, sum_max=50) == 1
        assert count_draws_matching_filters(consecutive_count=3) == 2
        assert count_draws_matching_filters(range_min_occupied=5) == 2
        assert count_draws_matching_filters(range_max_per_band=1) == 1


def test_bets_shows_draws_matching_current_filter_params() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Draw(contest=1, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6])),
                Draw(contest=2, n1=1, n2=3, n3=5, n4=7, n5=9, n6=11, **draw_parameters([1, 3, 5, 7, 9, 11])),
                Draw(contest=3, n1=10, n2=11, n3=20, n4=30, n5=40, n6=50, **draw_parameters([10, 11, 20, 30, 40, 50])),
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
                Draw(contest=1, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6])),
                Draw(contest=2, n1=1, n2=3, n3=5, n4=7, n5=9, n6=11, **draw_parameters([1, 3, 5, 7, 9, 11])),
                Draw(contest=3, n1=10, n2=11, n3=20, n4=30, n5=40, n6=50, **draw_parameters([10, 11, 20, 30, 40, 50])),
                Draw(contest=4, n1=10, n2=20, n3=30, n4=40, n5=50, n6=60, **draw_parameters([10, 20, 30, 40, 50, 60])),
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
    assert "101" in text
    assert "202" not in text
    assert "303" not in text

    response = app.test_client().get("/contests?consecutive_count=0")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Filtro ativo: maior sequência de números consecutivos = 0" in text
    assert "202" in text
    assert "101" not in text
    assert "303" not in text

    response = app.test_client().get("/contests?even_count=5")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Filtro ativo: quantidade de números pares = 5" in text
    assert "303" in text
    assert "101" not in text
    assert "202" not in text


def test_combinations_api_updates_from_generation_form_filters() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().get("/api/combinations?quantity=7&even_min=2&even_max=4")
    data = response.get_json()

    assert response.status_code == 200
    assert data["total"] == 50_063_860
    assert data["remaining"] == 40_325_950
    assert data["covered_combinations"] == 1


def test_combinations_api_uses_closure_numbers_for_coverage() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().get("/api/combinations?amount=3&quantity=6&closure_numbers=1+2+3+4+5+6+7")
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
        query_string={"amount": "3", "quantity": "6", "closure_numbers": "1 2 3 4 5 6 7 8 9 10"},
    ).get_json()
    comma_data = client.get(
        "/api/combinations",
        query_string={"amount": "3", "quantity": "6", "closure_numbers": "1,2,3,4,5,6,7,8,9,10"},
    ).get_json()

    assert space_data["closure_mode"] is True
    assert comma_data["closure_mode"] is True
    assert space_data["selected_amount"] == 210
    assert comma_data["selected_amount"] == 210
    assert space_data["covered_by_amount"] == 210
    assert comma_data["covered_by_amount"] == 210


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


def test_import_settings_save_default_generation_parameters() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.get("/import")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Configurações" in text
    assert 'name="bet_quantity"' in text
    assert 'name="generation_amount"' in text
    assert 'name="consecutive_count" min="0" max="6"' in text
    assert 'name="even_min" min="0" max="6"' in text
    assert 'name="even_max" min="0" max="6"' in text
    assert 'name="range_min_occupied" min="1" max="6"' in text
    assert 'name="range_max_per_band" min="1" max="6"' in text

    response = client.post(
        "/settings",
        data={
            "bet_quantity": "7",
            "generation_amount": "8",
            "consecutive_count": "3",
            "even_min": "2",
            "even_max": "4",
            "sum_min": "100",
            "sum_max": "220",
            "range_min_occupied": "4",
            "range_max_per_band": "2",
        },
        follow_redirects=True,
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Configurações salvas." in text
    with app.app_context():
        assert Config.query.filter_by(key="bet_quantity").one().value == "7"
        assert Config.query.filter_by(key="range_min_occupied").one().value == "4"
        assert get_config_values()["generation_amount"] == "8"

    response = client.get("/bets")
    text = response.get_data(as_text=True)

    assert 'type="hidden" name="quantity" value="7"' in text
    assert 'name="amount" min="1" max="100" value="8"' in text
    assert 'name="consecutive_count" min="0" max="6" placeholder="Opcional" value="3"' in text
    assert 'name="even_min" min="0" max="6" placeholder="Opcional" value="2"' in text
    assert 'name="even_max" min="0" max="6" placeholder="Opcional" value="4"' in text
    assert 'name="sum_min" min="0" placeholder="Opcional" value="100"' in text
    assert 'name="sum_max" min="0" placeholder="Opcional" value="220"' in text
    assert 'name="range_min_occupied" min="1" max="6" placeholder="Opcional" value="4"' in text
    assert 'name="range_max_per_band" min="1" max="6" placeholder="Opcional" value="2"' in text


def test_generation_params_are_restored_and_can_be_cleared() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.get("/rationale?amount=9&consecutive_count=3&even_min=2&even_max=4")
    assert response.status_code == 200

    response = client.get("/bets")
    text = response.get_data(as_text=True)
    assert 'name="amount" min="1" max="100" value="9"' in text
    assert 'name="consecutive_count" min="0" max="6" placeholder="Opcional" value="3"' in text
    assert 'name="even_min" min="0" max="6" placeholder="Opcional" value="2"' in text
    assert 'name="even_max" min="0" max="6" placeholder="Opcional" value="4"' in text

    response = client.get("/bets/clear", follow_redirects=True)
    text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'name="amount" min="1" max="100" value="9"' in text
    assert 'name="consecutive_count" min="0" max="6" placeholder="Opcional" value=""' in text
    assert 'name="even_min" min="0" max="6" placeholder="Opcional" value=""' in text


def test_even_max_lower_than_even_min_is_equalized_to_minimum() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().get("/rationale?even_min=5&even_max=2")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "even_min=5" in text
    assert "even_max=5" in text
    assert "5 a 5" in text


def test_clear_generation_filters_overrides_config_defaults() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.post(
        "/settings",
        data={
            "bet_quantity": "6",
            "generation_amount": "8",
            "consecutive_count": "3",
            "even_min": "2",
            "even_max": "4",
            "sum_min": "100",
            "sum_max": "220",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    response = client.get("/bets")
    text = response.get_data(as_text=True)
    assert 'name="consecutive_count" min="0" max="6" placeholder="Opcional" value="3"' in text
    assert 'name="even_min" min="0" max="6" placeholder="Opcional" value="2"' in text

    response = client.get("/bets/clear", follow_redirects=True)
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="amount" min="1" max="100" value="8"' in text
    assert 'name="consecutive_count" min="0" max="6" placeholder="Opcional" value=""' in text
    assert 'name="even_min" min="0" max="6" placeholder="Opcional" value=""' in text
    assert 'name="even_max" min="0" max="6" placeholder="Opcional" value=""' in text
    assert 'name="sum_min" min="0" placeholder="Opcional" value=""' in text
    assert 'name="sum_max" min="0" placeholder="Opcional" value=""' in text


def test_saved_bets_are_grouped_by_generation() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

        first_saved, first_generation = save_generated_bets(6, ["1,2,3,4,5,6", "7,8,9,10,11,12"])
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


def test_bets_can_generate_mathematical_closure_from_base_numbers() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().post(
        "/bets",
        data={
            "action": "closure",
            "quantity": "6",
            "amount": "5",
            "closure_numbers": "1 2 3 4 5 6 7",
        },
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "7 apostas geradas pelo fechamento matemático." in text
    assert "01" in text
    assert "07" in text
    assert 'name="bet" value="1,2,3,4,5,6"' in text
    assert 'name="bet" value="2,3,4,5,6,7"' in text


def test_bets_summary_uses_closure_labels_when_closure_numbers_are_present() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().get("/bets?amount=3&quantity=6&closure_numbers=1+2+3+4+5+6+7")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Apostas no fechamento" in text
    assert "Chance no fechamento" in text


def test_rationale_uses_closure_numbers_and_preserves_field_on_return() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().get("/rationale?amount=3&quantity=6&even_min=2&closure_numbers=1+2+3+4+5+6+7")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Resumo dos filtros" not in text
    assert "Quantidade de apostas = C(7, 6) = 7" in text
    assert "Nesse modo, os filtros da aba de geração ficam opcionais" in text
    assert "amount=3" in text
    assert "closure_numbers=1+2+3+4+5+6+7" in text


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
    assert "5. Distribuição por faixas" in text
    assert "Divide as dezenas em blocos" not in text
    assert "frequency-y-axis-title" not in text
    assert "frequency-x-axis-title" not in text
    assert "sum-y-axis-title" not in text
    assert "sum-x-axis-title" not in text
    assert "frequency-sequence" in text
    assert "chart-panel" in text
    assert "dashboard-chart-panel" in text
    assert text.index("Quantidade de números pares") < text.index("Maior sequência consecutiva")
    assert text.index("Maior sequência consecutiva") < text.index("5. Distribuição por faixas")
    assert text.index("5. Distribuição por faixas") < text.index("Mais frequentes")
    assert text.index("Mais frequentes") < text.index("Frequência x Soma dos Números Sorteados")
    assert text.index("Mais frequentes") < text.index("Frequência X Número Sorteado")


# ---------------------------------------------------------------------------
# Testes das melhorias implementadas
# ---------------------------------------------------------------------------


def test_import_rejects_non_xlsx_files() -> None:
    """Upload de arquivo com extensão não permitida deve ser rejeitado com flash."""
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.post(
        "/import",
        data={"file": (BytesIO(b"dummy content"), "resultados.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Formato inválido" in text


def test_import_rejects_missing_file() -> None:
    """POST sem arquivo deve redirecionar com flash de validação."""
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.post("/import", data={}, follow_redirects=True)
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Selecione uma planilha" in text


def test_import_handles_corrupted_xlsx_gracefully() -> None:
    """Arquivo .xlsx corrompido deve ser tratado com flash amigável, sem exceção."""
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.post(
        "/import",
        data={"file": (BytesIO(b"not an xlsx file at all"), "resultados.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Não foi possível ler o arquivo" in text


def test_import_service_raises_runtime_error_on_bad_workbook() -> None:
    """import_results_from_xlsx deve emitir RuntimeError para arquivos inválidos."""
    try:
        import_results_from_xlsx(BytesIO(b"garbage"))
        assert False, "Deveria ter levantado RuntimeError"
    except RuntimeError as exc:
        assert "Não foi possível ler o arquivo" in str(exc)


def test_format_int_and_format_percent_are_public() -> None:
    """format_int e format_percent devem ser exportadas pelo módulo services."""
    from app.services import format_int, format_percent

    assert format_int(1_000_000) == "1.000.000"
    assert format_int(0) == "0"
    assert format_percent(0.123456789) == "0,12345679"
    assert format_percent(100.0) == "100"


def test_reset_logs_counts_and_clears_all_data() -> None:
    """Rota /reset deve apagar concursos e apostas e emitir flash de confirmação."""
    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add(Draw(contest=1, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6])))
        db.session.commit()

    response = app.test_client().post("/reset", follow_redirects=True)
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Base reiniciada" in text
    with app.app_context():
        assert Draw.query.count() == 0


def test_refresh_draw_parameters_skips_empty_database() -> None:
    """refresh_draw_parameters deve retornar 0 imediatamente quando não há concursos."""
    from app.services import refresh_draw_parameters

    app = make_app()
    with app.app_context():
        db.create_all()
        result = refresh_draw_parameters()

    assert result == 0


# ---------------------------------------------------------------------------
# Frequência recente (feature: seletor de período no dashboard)
# ---------------------------------------------------------------------------


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
    assert "/api/recent-frequency" in text
