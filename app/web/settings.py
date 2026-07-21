"""Rotas de configuracao e manutencao local."""

from __future__ import annotations

import logging

from flask import flash, redirect, render_template, request, url_for

from ..settings.service import reset_all_data
from ..services import get_config_values, update_config_values
from . import bp


_log = logging.getLogger(__name__)


@bp.get("/settings")
def settings_page():
    return render_template("settings.html", config_values=get_config_values())


@bp.post("/settings")
def save_settings():
    update_config_values(request.form)
    _log.info("Configuracoes de geracao atualizadas.")
    flash("Configurações salvas.")
    return redirect(url_for("web.settings_page"))


@bp.post("/reset")
def reset_database():
    draw_count, bet_count = reset_all_data()
    _log.warning("Base reiniciada: %d concursos e %d apostas apagados.", draw_count, bet_count)
    flash("Base reiniciada: concursos e apostas apagados.")
    return redirect(url_for("web.settings_page"))
