"""Rotas de gerenciamento de usuários (criar, redefinir senha, ativar/desativar)."""

from __future__ import annotations

import logging

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sharedauth.access import requer_papel

from ..accounts.service import (
    MIN_PASSWORD_LENGTH,
    ROLE_ADMIN,
    ROLE_OPERADOR,
    list_users,
    set_active,
    set_role,
)
from ..accounts.service import create_user as create_account
from ..accounts.service import reset_password as reset_account_password
from ..extensions import db
from ..models import User
from . import bp
from .helpers import is_htmx_request, render_vary

_log = logging.getLogger(__name__)


# A mecânica de recusa (403, nunca redirect para o login) vem de
# `sharedauth.access.requer_papel`, compartilhada com o ControleRendaVariavel.
# Quem decide o que é ser administrador continua aqui: a biblioteca não conhece
# o modelo de usuário deste projeto.
#
# `is_authenticated` continua na condição de propósito, embora `requer_login`
# já garanta sessão em toda rota não pública: `current_user` é anônimo quando
# não há sessão, e `is_admin` não existe no anônimo do Flask-Login. Sem a
# primeira metade, um erro futuro na lista de endpoints públicos viraria
# AttributeError (500) em vez de 403.
#
# `prefixo_api=None` porque este app não serve rotas `/api/` -- ver o mesmo
# argumento em `create_app`.
admin_required = requer_papel(
    lambda: current_user.is_authenticated and current_user.is_admin,
    prefixo_api=None,
    mensagem="Apenas administradores podem gerir usuários.",
)


def _get_user_or_404(user_id: int) -> User:
    usuario = db.session.get(User, user_id)
    if usuario is None:
        abort(404)
    return usuario


def _users_feedback(message: str, *, severidade: str = "error"):
    """Devolve o resultado de uma ação sobre usuário, como toast.

    `severidade` por parâmetro em vez de inferida do texto: os chamadores já
    sabem se a operação deu certo, e adivinhar pela mensagem seria mais
    frágil. Padrão "error" porque a maioria das chamadas aqui é caminho de
    exceção (`ValueError`); os três sucessos abaixo passam "success"
    explicitamente.
    """
    if is_htmx_request():
        return render_vary(
            "users/_feedback.html",
            avisos=[{"mensagem": message, "severidade": severidade}],
            users=list_users(),
            min_password_length=MIN_PASSWORD_LENGTH,
        )
    flash(message, severidade)
    return redirect(url_for("web.users_page"))


@bp.get("/usuarios")
@admin_required
def users_page():
    return render_template(
        "users/index.html",
        users=list_users(),
        min_password_length=MIN_PASSWORD_LENGTH,
        roles=(ROLE_OPERADOR, ROLE_ADMIN),
    )


@bp.post("/usuarios")
@admin_required
def create_user():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    role = request.form.get("role", ROLE_OPERADOR)
    try:
        create_account(username, password, role=role, actor=current_user)
    except ValueError as exc:
        return _users_feedback(str(exc))
    _log.info("Usuario criado.")
    return _users_feedback(f"Usuário '{username.strip()}' criado.", severidade="success")


@bp.post("/usuarios/<int:user_id>/senha")
@admin_required
def reset_user_password(user_id: int):
    usuario = _get_user_or_404(user_id)
    password = request.form.get("password", "")
    try:
        reset_account_password(usuario, password, actor=current_user)
    except ValueError as exc:
        return _users_feedback(str(exc))
    return _users_feedback(f"Senha de '{usuario.username}' redefinida.", severidade="success")


@bp.post("/usuarios/<int:user_id>/ativo")
@admin_required
def toggle_user_active(user_id: int):
    usuario = _get_user_or_404(user_id)
    active = request.form.get("active") == "1"
    if not active and usuario.id == current_user.id:
        return _users_feedback("Você não pode desativar sua própria conta.")
    try:
        set_active(usuario, active, actor=current_user)
    except ValueError as exc:
        return _users_feedback(str(exc))
    estado = "ativado" if active else "desativado"
    return _users_feedback(f"Usuário '{usuario.username}' {estado}.", severidade="success")


@bp.post("/usuarios/<int:user_id>/papel")
@admin_required
def change_user_role(user_id: int):
    usuario = _get_user_or_404(user_id)
    role = request.form.get("role", "")
    try:
        set_role(usuario, role, actor=current_user)
    except ValueError as exc:
        return _users_feedback(str(exc))
    nome = "administrador" if role == ROLE_ADMIN else "operador"
    return _users_feedback(
        f"Usuário '{usuario.username}' agora é {nome}.", severidade="success"
    )
