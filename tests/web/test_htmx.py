from __future__ import annotations

from app import db
from app.core.numbers import draw_parameters
from app.models import Draw
from tests.support import csrf_form_data, make_app, workbook_bytes


def _add_draws() -> None:
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
                n1=1,
                n2=3,
                n3=5,
                n4=7,
                n5=9,
                n6=11,
                **draw_parameters([1, 3, 5, 7, 9, 11]),
            ),
        ]
    )
    db.session.commit()


def test_dashboard_htmx_response_is_cache_safe_fragment() -> None:
    app = make_app()
    with app.app_context():
        _add_draws()

    response = app.test_client().get(
        "/dashboard?count=10", headers={"HX-Request": "true"}
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="dashboard-content"' in text
    assert "<!doctype html>" not in text.lower()
    assert "HX-Request" in response.headers["Vary"]
    assert 'hx-push-url="true"' in text

    full_response = app.test_client().get("/dashboard?count=10")
    assert "HX-Request" in full_response.headers["Vary"]


def test_contests_htmx_filter_keeps_normal_navigation_contract() -> None:
    app = make_app()
    with app.app_context():
        _add_draws()

    response = app.test_client().get(
        "/contests?winners_only=1", headers={"HX-Request": "true"}
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="contests-results"' in text
    assert "<!doctype html>" not in text.lower()
    assert "HX-Request" in response.headers["Vary"]
    assert "<td>1</td>" in text
    assert "<td>2</td>" not in text
    assert 'hx-trigger="change from:input"' in text


def test_settings_htmx_post_returns_feedback_without_redirect() -> None:
    app = make_app()
    client = app.test_client()

    response = client.post(
        "/settings",
        data=csrf_form_data(
            client,
            "/settings",
            {"bet_quantity": "6", "generation_amount": "5"},
        ),
        headers={"HX-Request": "true"},
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="settings-feedback"' in text
    assert "Configurações salvas." in text
    assert "HX-Request" in response.headers["Vary"]
    assert response.headers.get("Location") is None


def test_bets_preview_is_one_server_rendered_fragment() -> None:
    app = make_app()
    with app.app_context():
        _add_draws()

    response = app.test_client().get(
        "/bets/preview?amount=3&even_min=2&even_max=4",
        headers={"HX-Request": "true"},
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="bets-preview"' in text
    assert "Concursos no BD que passariam" in text
    assert "Resumo dos filtros" in text
    assert "<!doctype html>" not in text.lower()
    assert "HX-Request" in response.headers["Vary"]


def test_filter_targets_fragment_uses_oob_inputs_and_refresh_event() -> None:
    app = make_app()
    with app.app_context():
        _add_draws()

    response = app.test_client().get(
        "/bets/filter-targets/fragment?target_percentage=80",
        headers={"HX-Request": "true"},
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="filter-even-min"' in text
    assert 'hx-swap-oob="outerHTML"' in text
    assert response.headers["HX-Trigger"] == "bets-preview"


def test_bets_htmx_generation_and_closure_keep_server_save_contract() -> None:
    app = make_app()
    client = app.test_client()

    response = client.post(
        "/bets",
        data=csrf_form_data(client, "/bets", {"action": "generate", "amount": "1"}),
        headers={"HX-Request": "true"},
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="generation-result"' in text
    assert 'hx-post="/bets"' in text
    assert "Location" not in response.headers

    response = client.post(
        "/bets",
        data=csrf_form_data(
            client,
            "/bets",
            {
                "action": "closure",
                "closure_numbers": "1,2,3,4,5,6,7",
                "amount": "1",
            },
        ),
        headers={"HX-Request": "true"},
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'name="action" value="save_closure"' in text
    assert 'name="closure_numbers" value="1,2,3,4,5,6,7"' in text
    assert 'name="bet"' not in text


def test_contests_htmx_upload_uses_multipart_feedback_and_refreshes_list() -> None:
    app = make_app()
    client = app.test_client()
    payload = csrf_form_data(client, "/contests")
    payload["file"] = (
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
                    "R$0,00",
                    "R$0,00",
                    "R$0,00",
                    "R$0,00",
                ]
            ]
        ),
        "concursos.xlsx",
    )

    response = client.post(
        "/contests/import",
        data=payload,
        headers={"HX-Request": "true"},
    )
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="import-feedback"' in text
    assert "Importação concluída" in text
    assert 'id="contests-results"' in text
    assert 'hx-swap-oob="outerHTML"' in text
