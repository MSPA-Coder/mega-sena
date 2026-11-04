"""Rotas de configuracao e manutencao local.

Desde 04/11/2026 (ADR 0004) a tela e de todos: os padroes de geracao sao de
cada conta, e cada pessoa ajusta os proprios. O que e "como o sistema
funciona" continua de administrador: o endereco da planilha de resultados
(`save_system_settings`), que vale para todo mundo, e `reset_database`, que
apaga TODOS os concursos e as apostas de todas as contas. Para quem nao e
admin essas duas secoes nem aparecem, e as rotas recusam com 403.
"""

from __future__ import annotations

import logging

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..audit.contracts import AuditContext
from ..audit.service import record_event
from ..bets.criteria import GENERATION_LIMITS
from ..settings.commands import reset_all_data, update_generation_values, update_results_source_url
from ..settings.service import get_generation_values, get_results_source_url
from . import bp
from .authorization import admin_required
from .helpers import audit_request_context, is_htmx_request

_log = logging.getLogger(__name__)


def _feedback(mensagem: str, severidade: str, *, alvo: str = "settings-feedback"):
    """Toast do resultado; `alvo` e o ponto de swap da secao que enviou."""
    if is_htmx_request():
        return render_template(
            "settings/_feedback.html",
            avisos=[{"mensagem": mensagem, "severidade": severidade}],
            feedback_id=alvo,
        )
    flash(mensagem, severidade)
    return redirect(url_for("web.settings_page"))


@bp.get("/settings")
def settings_page():
    return render_template(
        "settings/index.html",
        config_values=get_generation_values(current_user.id),
        results_source_url=get_results_source_url() if current_user.is_admin else None,
        generation_limits=GENERATION_LIMITS,
    )


@bp.post("/settings")
def save_settings():
    """Padroes de geracao da propria conta."""
    try:
        update_generation_values(
            current_user.id,
            request.form,
            audit=AuditContext(current_user.id, audit_request_context()),
        )
    except ValueError as exc:
        record_event(
            action="settings.update",
            entity="user_config",
            entity_id=current_user.id,
            actor=current_user,
            success=False,
            context=audit_request_context(),
        )
        return _feedback(str(exc), "error")
    _log.info("Padroes de geracao atualizados pela conta %s.", current_user.id)
    return _feedback("Configurações salvas.", "success")


@bp.post("/settings/sistema")
@admin_required
def save_system_settings():
    """Endereco da planilha de resultados, que vale para todas as contas."""
    try:
        update_results_source_url(
            request.form.get("results_source_url"),
            audit=AuditContext(current_user.id, audit_request_context()),
        )
    except ValueError as exc:
        record_event(
            action="settings.update_system",
            entity="config",
            actor=current_user,
            success=False,
            context=audit_request_context(),
        )
        return _feedback(str(exc), "error", alvo="system-feedback")
    _log.info("Endereco da planilha de resultados atualizado.")
    return _feedback("Endereço da planilha salvo.", "success", alvo="system-feedback")


@bp.post("/reset")
@admin_required
def reset_database():
    draw_count, bet_count = reset_all_data(
        audit=AuditContext(current_user.id, audit_request_context())
    )
    _log.warning("Base reiniciada: %d concursos e %d apostas apagados.", draw_count, bet_count)
    return _feedback(
        "Base reiniciada: concursos e apostas de todas as contas apagados.",
        "success",
        alvo="system-feedback",
    )
