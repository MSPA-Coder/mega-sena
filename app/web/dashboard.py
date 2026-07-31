"""Rotas da pagina e APIs do dashboard."""

from __future__ import annotations

from flask import jsonify, redirect, request, url_for

from ..draws.statistics import build_stats
from . import bp
from .helpers import is_htmx_request, optional_int, render_htmx, render_page


_DASHBOARD_PERIODS = (
    (None, "Todos"),
    (2000, "Últ. 2000"),
    (1000, "Últ. 1000"),
    (500, "Últ. 500"),
    (200, "Últ. 200"),
    (100, "Últ. 100"),
    (50, "Últ. 50"),
    (10, "Últ. 10"),
)


@bp.get("/")
def home():
    return redirect(url_for("web.dashboard"))


@bp.get("/dashboard")
def dashboard():
    selected_count = _bounded_period()
    stats = build_stats(selected_count)
    context = {
        "stats": stats,
        "selected_count": selected_count,
        "periods": _DASHBOARD_PERIODS,
    }
    if is_htmx_request():
        return render_htmx("dashboard/_content.html", **context)
    return render_page("dashboard/index.html", **context)


def _bounded_period() -> int | None:
    raw = request.args.get("count", "").strip()
    count = optional_int(raw) if raw else None
    return max(10, min(count, 10_000)) if count is not None else None


@bp.get("/api/dashboard-stats")
def dashboard_stats():
    """Retorna o dashboard completo para o periodo selecionado."""
    stats = build_stats(_bounded_period())
    payload = {
        "count": stats["count"],
        "actual_count": stats["actual_count"],
        "total_draws": stats["total_draws"],
        "mega_sena_games_with_winners": stats["mega_sena_games_with_winners"],
        "mega_sena_games_without_winners": stats["mega_sena_games_without_winners"],
        "mega_sena_games_with_winners_pct": stats["mega_sena_games_with_winners_pct"],
        "mega_sena_games_without_winners_pct": stats["mega_sena_games_without_winners_pct"],
        "prize_cards": stats["prize_cards"],
        "even_distribution": stats["even_distribution"],
        "consecutive_distribution": stats["consecutive_distribution"],
        "ranges": stats["ranges"],
        "most_frequent": stats["most_frequent"],
        "least_frequent": stats["least_frequent"],
        "frequency": stats["frequency"],
        "sum_histogram": stats["sum_histogram"],
    }
    return jsonify(payload)
