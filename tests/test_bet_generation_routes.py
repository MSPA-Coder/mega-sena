from __future__ import annotations

from app.web import bets


def test_filter_targets_fragment_returns_response_with_trigger_header(app, monkeypatch):
    monkeypatch.setattr(
        bets,
        "calculate_individual_filter_targets",
        lambda percentage: {
            "total": 0,
            "target_percentage": percentage,
            "parameters": {
                key: {"value": None} for key in bets.GENERATION_FILTER_KEYS
            },
        },
    )

    with app.test_request_context(
        "/bets/filter-targets/fragment?target_percentage=80"
    ):
        response = bets.filter_targets_fragment()

    assert response.status_code == 200
    assert response.headers["HX-Trigger-After-Settle"] == "bets-preview"
    assert "Importe concursos" in response.get_data(as_text=True)
