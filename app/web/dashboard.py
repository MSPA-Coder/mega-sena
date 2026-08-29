"""Rotas do dashboard."""

from __future__ import annotations

from flask import redirect, render_template, request, url_for

from ..draws.statistics import build_stats
from . import bp
from .helpers import is_htmx_request, optional_int

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
        return render_template("dashboard/_content.html", **context)
    return render_template("dashboard/index.html", **context)


def _bounded_period() -> int | None:
    raw = request.args.get("count", "").strip()
    count = optional_int(raw) if raw else None
    return max(10, min(count, 10_000)) if count is not None else None
