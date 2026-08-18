"""Rotas de configuracao e manutencao local."""

from __future__ import annotations

import logging

from flask import flash, redirect, render_template, request, url_for

from ..bets.criteria import GENERATION_LIMITS
from ..settings.service import get_config_values, reset_all_data, update_config_values
from . import bp
from .helpers import is_htmx_request, render_vary

_log = logging.getLogger(__name__)


@bp.get("/settings")
def settings_page():
    return render_template(
        "settings/index.html",
        config_values=get_config_values(),
        generation_limits=GENERATION_LIMITS,
    )


@bp.post("/settings")
def save_settings():
    try:
        update_config_values(request.form)
    except ValueError as exc:
        if is_htmx_request():
            return render_vary("settings/_feedback.html", message=str(exc))
        flash(str(exc))
        return redirect(url_for("web.settings_page"))
    _log.info("Configuracoes atualizadas.")
    if is_htmx_request():
        return render_vary(
            "settings/_feedback.html", message="Configurações salvas."
        )
    flash("Configurações salvas.")
    return redirect(url_for("web.settings_page"))


@bp.post("/reset")
def reset_database():
    draw_count, bet_count = reset_all_data()
    _log.warning("Base reiniciada: %d concursos e %d apostas apagados.", draw_count, bet_count)
    message = "Base reiniciada: concursos e apostas apagados."
    if is_htmx_request():
        return render_vary("settings/_feedback.html", message=message)
    flash(message)
    return redirect(url_for("web.settings_page"))
