from __future__ import annotations

from datetime import date
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app import db
from app.core.numbers import MAX_INT32
from app.draws.importing import import_results_from_xlsx
from app.models import Config, Draw
from app.settings.service import get_config_values
from tests.support import csrf_form_data, make_app, workbook_bytes


def test_import_recalculates_bad_sheet_dimensions() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
        first = import_results_from_xlsx(
            workbook_bytes(
                [
                    [
                        1,
                        "01/01/2026",
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                        0,
                        10,
                        100,
                        "R$0,00",
                        "R$1,00",
                        "R$2,00",
                        "R$3,00",
                    ],
                ]
            )
        )
        second = import_results_from_xlsx(
            workbook_bytes(
                [
                    [
                        1,
                        "01/01/2026",
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                        0,
                        10,
                        100,
                        "R$0,00",
                        "R$1,00",
                        "R$2,00",
                        "R$3,00",
                    ],
                    [
                        2,
                        "02/01/2026",
                        7,
                        8,
                        9,
                        10,
                        11,
                        12,
                        1,
                        20,
                        200,
                        "R$4,00",
                        "R$5,00",
                        "R$6,00",
                        "R$7,00",
                    ],
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
                    [
                        1,
                        "01/01/2026",
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                        0,
                        10,
                        100,
                        "R$0,00",
                        "R$1,00",
                        "R$2,00",
                        "R$3,00",
                    ],
                ]
            )
        )
        result = import_results_from_xlsx(
            workbook_bytes(
                [
                    [
                        1,
                        "01/01/2026",
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                        1,
                        11,
                        101,
                        "R$8,00",
                        "R$9,00",
                        "R$10,00",
                        "R$11,00",
                    ],
                ]
            )
        )

        draw = Draw.query.filter_by(contest=1).one()
        assert result == {"imported": 0, "updated": 1, "ignored": 0}
        assert draw.winners_6 == 1
        assert draw.winners_5 == 11
        assert draw.prize_cents == 800


def test_minimal_reimport_preserves_existing_optional_metadata() -> None:
    """Uma planilha sem colunas opcionais só atualiza dezenas e derivados."""
    from openpyxl import Workbook

    app = make_app()
    with app.app_context():
        db.create_all()
        import_results_from_xlsx(
            workbook_bytes(
                [
                    [
                        1,
                        "01/01/2026",
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                        2,
                        3,
                        4,
                        "10,00",
                        "20,00",
                        "30,00",
                        "40,00",
                    ]
                ]
            )
        )

        workbook = Workbook()
        sheet = workbook.active
        sheet.append(
            ["Concurso", "Bola1", "Bola2", "Bola3", "Bola4", "Bola5", "Bola6"]
        )
        sheet.append([1, 10, 11, 12, 13, 14, 15])
        minimal = BytesIO()
        workbook.save(minimal)
        minimal.seek(0)

        result = import_results_from_xlsx(minimal)
        draw = Draw.query.filter_by(contest=1).one()

        assert result == {"imported": 0, "updated": 1, "ignored": 0}
        assert draw.numbers == [10, 11, 12, 13, 14, 15]
        assert (draw.draw_date, draw.winners_6, draw.winners_5, draw.winners_4) == (
            date(2026, 1, 1),
            2,
            3,
            4,
        )
        assert (
            draw.prize_cents,
            draw.quina_rateio_cents,
            draw.quadra_rateio_cents,
            draw.accumulated_cents,
        ) == (1_000, 2_000, 3_000, 4_000)


def test_malformed_money_aborts_import_without_overwriting_existing_draws() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
        import_results_from_xlsx(
            workbook_bytes(
                [
                    [
                        1,
                        "01/01/2026",
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                        0,
                        0,
                        0,
                        "10,00",
                        "0",
                        "0",
                        "0",
                    ]
                ]
            )
        )

        with pytest.raises(RuntimeError, match="Valor monetário inválido"):
            import_results_from_xlsx(
                workbook_bytes(
                    [
                        [
                            1,
                            "01/01/2026",
                            7,
                            8,
                            9,
                            10,
                            11,
                            12,
                            0,
                            0,
                            0,
                            "20,00",
                            "0",
                            "0",
                            "0",
                        ],
                        [
                            2,
                            "02/01/2026",
                            13,
                            14,
                            15,
                            16,
                            17,
                            18,
                            0,
                            0,
                            0,
                            "não é dinheiro",
                            "0",
                            "0",
                            "0",
                        ],
                    ]
                )
            )

        draw = Draw.query.filter_by(contest=1).one()
        assert Draw.query.count() == 1
        assert draw.numbers == [1, 2, 3, 4, 5, 6]
        assert draw.prize_cents == 1_000


@pytest.mark.parametrize(
    ("column_index", "invalid_value", "message"),
    [
        (1, "31/02/2026", "Data inválida"),
        (8, "muitos", "Quantidade inválida"),
    ],
)
def test_malformed_optional_metadata_aborts_without_overwriting_existing_draw(
    column_index: int, invalid_value: object, message: str
) -> None:
    app = make_app()
    with app.app_context():
        import_results_from_xlsx(
            workbook_bytes(
                [
                    [
                        1,
                        "01/01/2026",
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                        2,
                        3,
                        4,
                        "10,00",
                        "20,00",
                        "30,00",
                        "40,00",
                    ]
                ]
            )
        )
        replacement = [
            1,
            "02/02/2026",
            7,
            8,
            9,
            10,
            11,
            12,
            5,
            6,
            7,
            "50,00",
            "60,00",
            "70,00",
            "80,00",
        ]
        replacement[column_index] = invalid_value

        with pytest.raises(RuntimeError, match=message):
            import_results_from_xlsx(workbook_bytes([replacement]))

        draw = Draw.query.filter_by(contest=1).one()
        assert draw.numbers == [1, 2, 3, 4, 5, 6]
        assert draw.draw_date == date(2026, 1, 1)
        assert (draw.winners_6, draw.winners_5, draw.winners_4) == (2, 3, 4)


def test_import_settings_save_default_generation_parameters() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.get("/settings")
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
        data=csrf_form_data(
            client,
            "/settings",
            {
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
        ),
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
    assert (
        'name="consecutive_count" min="0" max="6" placeholder="Opcional" value="3"'
        in text
    )
    assert 'name="even_min" min="0" max="6" placeholder="Opcional" value="2"' in text
    assert 'name="even_max" min="0" max="6" placeholder="Opcional" value="4"' in text
    assert 'name="sum_min" min="0" max="345" placeholder="Opcional" value="100"' in text
    assert 'name="sum_max" min="0" max="345" placeholder="Opcional" value="220"' in text
    assert (
        'name="range_min_occupied" min="1" max="6" placeholder="Opcional" value="4"'
        in text
    )
    assert (
        'name="range_max_per_band" min="1" max="6" placeholder="Opcional" value="2"'
        in text
    )


def test_import_rejects_non_xlsx_files() -> None:
    """Upload de arquivo com extensão não permitida deve ser rejeitado com flash."""
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.post(
        "/contests/import",
        data=csrf_form_data(
            client, "/contests", {"file": (BytesIO(b"dummy content"), "resultados.csv")}
        ),
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
    response = client.post(
        "/contests/import",
        data=csrf_form_data(client, "/contests"),
        follow_redirects=True,
    )
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
        "/contests/import",
        data=csrf_form_data(
            client,
            "/contests",
            {"file": (BytesIO(b"not an xlsx file at all"), "resultados.xlsx")},
        ),
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


def test_import_rejects_xlsx_with_excessive_uncompressed_size(monkeypatch) -> None:
    """Um XLSX pequeno e altamente expansível deve ser barrado antes do parser XML."""
    import app.draws.importing as importing_service

    stream = workbook_bytes([])
    with ZipFile(stream, "a", ZIP_DEFLATED) as archive:
        archive.writestr("xl/padding.bin", b"x" * 4_096)
    stream.seek(0)
    monkeypatch.setattr(importing_service, "MAX_XLSX_UNCOMPRESSED_BYTES", 1_024)

    with pytest.raises(RuntimeError, match="grande demais"):
        import_results_from_xlsx(stream)


def test_import_rejects_fractional_or_negative_contests_and_normalizes_money() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
        result = import_results_from_xlsx(
            workbook_bytes(
                [
                    [
                        1.5,
                        "01/01/2026",
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                        1,
                        1,
                        1,
                        "1,00",
                        "1,00",
                        "1,00",
                        "1,00",
                    ],
                    [
                        -2,
                        "01/01/2026",
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                        1,
                        1,
                        1,
                        "1,00",
                        "1,00",
                        "1,00",
                        "1,00",
                    ],
                    [
                        3,
                        "01/01/2026",
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                        0,
                        0,
                        0,
                        "1234.56",
                        "1.234,56",
                        "0",
                        "0",
                    ],
                ]
            )
        )
        draw = Draw.query.one()

        assert result == {"imported": 1, "updated": 0, "ignored": 2}
        assert draw.contest == 3
        assert (draw.winners_6, draw.winners_5, draw.winners_4) == (0, 0, 0)
        assert draw.prize_cents == 123_456
        assert draw.quina_rateio_cents == 123_456
        assert draw.accumulated_cents == 0
        assert draw.quadra_rateio_cents == 0


def test_import_ignores_rows_beyond_postgres_integer_range() -> None:
    """Draw.contest e Draw.winners_* são colunas db.Integer (int4 no
    PostgreSQL). Um contest que caiba em um int64 mas estoure um int32 deve
    descartar a linha, em vez de propagar até o INSERT e derrubar o lote
    inteiro com "integer out of range". Um winners_* explícito fora do intervalo
    é inválido e interrompe atomicamente a importação."""
    app = make_app()
    with app.app_context():
        db.create_all()
        with pytest.raises(RuntimeError, match="Quantidade inválida"):
            import_results_from_xlsx(
                workbook_bytes(
                    [
                        [
                            MAX_INT32 + 1,
                            "01/01/2026",
                            1,
                            2,
                            3,
                            4,
                            5,
                            6,
                            1,
                            1,
                            1,
                            "1,00",
                            "1,00",
                            "1,00",
                            "1,00",
                        ],
                        [
                            4,
                            "01/01/2026",
                            1,
                            2,
                            3,
                            4,
                            5,
                            6,
                            MAX_INT32 + 1,
                            1,
                            1,
                            "1,00",
                            "1,00",
                            "1,00",
                            "1,00",
                        ],
                    ]
                )
            )

        assert Draw.query.count() == 0


def test_refresh_draw_parameters_skips_empty_database() -> None:
    """refresh_draw_parameters deve retornar 0 imediatamente quando não há concursos."""
    from app.draws.statistics import refresh_draw_parameters

    app = make_app()
    with app.app_context():
        db.create_all()
        result = refresh_draw_parameters()

    assert result == 0


def test_contests_page_exposes_xlsx_import_form() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    text = app.test_client().get("/contests").get_data(as_text=True)

    assert "Importar resultados" in text
    assert 'action="/contests/import"' in text
    assert 'accept=".xlsx"' in text
