from __future__ import annotations

from app import create_app, db
from app.core.numbers import (
    count_consecutive_numbers,
    count_even_numbers,
    count_occupied_range_bands,
    draw_parameters,
    max_range_band_count,
)
from app.draws.statistics import (
    build_stats,
    ensure_draw_parameters_current,
)
from app.models import Draw
from tests.support import make_app


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


def test_scripts_are_external_and_event_attributes_are_absent() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().get("/settings")
    text = response.get_data(as_text=True)
    assert '<script src="/static/base.js?v=' in text
    assert "<script nonce=" not in text
    assert "onclick=" not in text
    assert "onchange=" not in text


def test_formatters_use_brazilian_number_separators() -> None:
    from app.core.formatting import format_int, format_percent

    assert format_int(1_000_000) == "1.000.000"
    assert format_int(0) == "0"
    assert format_percent(0.123456789) == "0,12345679"
    assert format_percent(100.0) == "100"


def test_draw_parameters_refresh_runs_only_once_per_version() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()
        db.session.add(Draw(contest=1, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6))
        db.session.commit()

        assert ensure_draw_parameters_current() == 1
        assert ensure_draw_parameters_current() == 0
        draw = Draw.query.one()
        assert (draw.total_sum, draw.even_count, draw.consecutive_count) == (21, 3, 6)


def test_create_app_accepts_configuration_overrides() -> None:
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "factory-test",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )

    assert app.testing is True
    assert app.config["SECRET_KEY"] == "factory-test"
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"


def test_build_stats_with_no_count_considers_full_history() -> None:
    """Sem período informado, as estatísticas consideram todos os concursos."""
    app = make_app()
    with app.app_context():
        db.create_all()
        for contest in range(1, 11):
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

        stats = build_stats()

    assert stats["total_draws"] == 10
    assert stats["count"] is None
    assert stats["actual_count"] == 10


def test_build_stats_with_count_limits_to_recent_draws() -> None:
    """build_stats(count) deve considerar apenas os N concursos mais recentes."""
    app = make_app()
    with app.app_context():
        db.create_all()
        # 5 concursos com números pares "1-6", 5 concursos mais recentes com números "10-15"
        for contest in range(1, 6):
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
        for contest in range(6, 11):
            db.session.add(
                Draw(
                    contest=contest,
                    n1=10,
                    n2=11,
                    n3=12,
                    n4=13,
                    n5=14,
                    n6=15,
                    **draw_parameters([10, 11, 12, 13, 14, 15]),
                )
            )
        db.session.commit()

        stats = build_stats(5)

    assert stats["total_draws"] == 5
    assert stats["count"] == 5
    assert stats["frequency"][10] == 5
    assert stats["frequency"][1] == 0
