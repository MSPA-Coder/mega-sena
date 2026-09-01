"""Rotas de configuracao e manutencao local.

A tela inteira e de administrador. `reset_database` apaga TODOS os
concursos e apostas de uma vez, e os valores de `save_settings` mudam o
padrao com que todo mundo gera aposta -- as duas coisas sao 'como o
sistema funciona', nao 'operar o sistema'. O GET entra junto de proposito:
deixar o formulario visivel e recusar so o POST daria uma tela que existe
para nao funcionar.
"""

from __future__ import annotations

import logging

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..audit.service import record_event
from ..bets.criteria import GENERATION_LIMITS
from ..settings.service import get_config_values, reset_all_data, update_config_values
from . import bp
from .authorization import admin_required
from .helpers import audit_request_context, is_htmx_request

_log = logging.getLogger(__name__)


@bp.get("/settings")
@admin_required
def settings_page():
    return render_template(
        "settings/index.html",
        config_values=get_config_values(),
        generation_limits=GENERATION_LIMITS,
    )


@bp.post("/settings")
@admin_required
def save_settings():
    try:
        update_config_values(request.form)
    except ValueError as exc:
        record_event(action="settings.update", entity="config", actor=current_user, success=False, context=audit_request_context())
        if is_htmx_request():
            return render_template(
                "settings/_feedback.html",
                avisos=[{"mensagem": str(exc), "severidade": "error"}],
            )
        flash(str(exc), "error")
        return redirect(url_for("web.settings_page"))
    _log.info("Configuracoes atualizadas.")
    record_event(action="settings.update", entity="config", actor=current_user, success=True, context=audit_request_context())
    if is_htmx_request():
        return render_template(
            "settings/_feedback.html",
            avisos=[{"mensagem": "Configurações salvas.", "severidade": "success"}],
        )
    flash("Configurações salvas.", "success")
    return redirect(url_for("web.settings_page"))


@bp.post("/reset")
@admin_required
def reset_database():
    draw_count, bet_count = reset_all_data()
    _log.warning("Base reiniciada: %d concursos e %d apostas apagados.", draw_count, bet_count)
    message = "Base reiniciada: concursos e apostas apagados."
    record_event(action="data.reset", entity="draws_and_generated_bets", actor=current_user, success=True, context={**audit_request_context(), "draw_count": draw_count, "bet_count": bet_count})
    if is_htmx_request():
        return render_template(
            "settings/_feedback.html",
            avisos=[{"mensagem": message, "severidade": "success"}],
        )
    flash(message, "success")
    return redirect(url_for("web.settings_page"))
