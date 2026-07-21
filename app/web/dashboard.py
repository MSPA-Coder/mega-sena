"""Rotas da pagina e APIs do dashboard."""

from __future__ import annotations

from flask import jsonify, redirect, render_template, request, url_for

from ..draws.statistics import build_recent_frequency, build_stats
from . import bp
from .helpers import optional_int


@bp.get("/")
def home():
    return redirect(url_for("web.dashboard"))


@bp.get("/dashboard")
def dashboard():
    stats = build_stats()
    return render_template("dashboard.html", stats=stats)


def _bounded_period() -> int | None:
    raw = request.args.get("count", "").strip()
    count = optional_int(raw) if raw else None
    return max(10, min(count, 10_000)) if count is not None else None


@bp.get("/api/recent-frequency")
def recent_frequency():
    return jsonify(build_recent_frequency(_bounded_period()))


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
