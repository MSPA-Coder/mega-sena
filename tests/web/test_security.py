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
from tests.support import csrf_form_data, make_app, workbook_bytes  # noqa: F401


def test_mutating_forms_include_csrf_tokens_and_clear_uses_post() -> None:
    """Formulários que alteram estado devem levar token CSRF; limpar filtros não deve usar GET."""
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    settings_text = client.get("/settings").get_data(as_text=True)
    contests_text = client.get("/contests").get_data(as_text=True)
    bets_text = client.get("/bets").get_data(as_text=True)

    assert settings_text.count('name="_csrf_token"') >= 2
    assert 'name="_csrf_token"' in contests_text
    assert 'name="_csrf_token"' in bets_text
    assert 'formaction="/bets/clear"' in bets_text
    assert 'formmethod="post"' in bets_text
    assert client.get("/bets/clear").status_code == 405


def test_post_without_csrf_token_is_rejected() -> None:
    """POST sem token não deve executar ação destrutiva."""
    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add(Draw(contest=1, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6])))
        db.session.commit()

    response = app.test_client().post("/reset")

    assert response.status_code == 400
    with app.app_context():
        assert Draw.query.count() == 1


def test_security_headers_are_applied() -> None:
    """Respostas HTML devem sair com cabeçalhos defensivos básicos."""
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().get("/dashboard")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Referrer-Policy"] == "same-origin"
    assert "form-action 'self'" in response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'self'" in response.headers["Content-Security-Policy"]
    assert "object-src 'none'" in response.headers["Content-Security-Policy"]
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert "'nonce-" not in response.headers["Content-Security-Policy"]
    assert "script-src 'self' 'unsafe-inline'" not in response.headers["Content-Security-Policy"]
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert response.headers["X-Permitted-Cross-Domain-Policies"] == "none"


def test_reset_logs_counts_and_clears_all_data() -> None:
    """Rota /reset deve apagar concursos e apostas e emitir flash de confirmação."""
    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add(Draw(contest=1, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, **draw_parameters([1, 2, 3, 4, 5, 6])))
        db.session.commit()

    client = app.test_client()
    response = client.post("/reset", data=csrf_form_data(client, "/settings"), follow_redirects=True)
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Base reiniciada" in text
    with app.app_context():
        assert Draw.query.count() == 0


def test_factory_rejects_untrusted_host_headers() -> None:
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "factory-test",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )

    client = app.test_client()
    assert client.get("/dashboard", headers={"Host": "attacker.example"}).status_code == 400
    assert client.get("/dashboard", headers={"Host": "[::1]"}).status_code == 200
