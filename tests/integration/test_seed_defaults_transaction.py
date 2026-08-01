from __future__ import annotations

from app import db
from app.models import Config
from tests.support import make_app


def test_seed_defaults_rolls_back_defaults_when_parameter_refresh_fails(monkeypatch) -> None:
    app = make_app()

    def fail_refresh(*, commit: bool = True) -> int:
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(
        "app.draws.statistics.ensure_draw_parameters_current", fail_refresh
    )
    result = app.test_cli_runner().invoke(args=["seed-defaults"])

    assert result.exit_code != 0
    with app.app_context():
        assert Config.query.count() == 0
        db.session.remove()
