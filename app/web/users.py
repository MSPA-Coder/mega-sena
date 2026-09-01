"""Rotas de gerenciamento de usuários (criar, redefinir senha, ativar/desativar)."""

from __future__ import annotations

import logging

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

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
from ..audit.service import record_event
from ..extensions import db
from ..models import User
from . import bp
from .authorization import admin_required
from .helpers import audit_request_context, is_htmx_request

_log = logging.getLogger(__name__)


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
        return render_template(
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
        usuario = create_account(username, password, role=role, actor=current_user)
    except ValueError as exc:
        record_event(action="users.create", entity="user", actor=current_user, success=False, context=audit_request_context())
        return _users_feedback(str(exc))
    record_event(action="users.create", entity="user", entity_id=usuario.id, actor=current_user, success=True, context={**audit_request_context(), "username": username.strip(), "role": role})
    _log.info("Usuario criado.")
    return _users_feedback(f"Usuário '{username.strip()}' criado.", severidade="success")


@bp.post("/usuarios/<int:user_id>/senha")
@admin_required
def reset_user_password(user_id: int):
    """Redefine a senha de outra conta e mostra a senha temporária gerada.

    A resposta não usa `_users_feedback`: aquilo vira toast, e toast some. A
    senha temporária é a única cópia em texto claro que vai existir -- ela
    precisa ficar na tela até quem redefiniu sair da página.

    Pelo mesmo motivo o caminho sem HTMX **renderiza** a página em vez de
    redirecionar: um redirect perderia o valor no caminho.
    """
    usuario = _get_user_or_404(user_id)
    try:
        senha_temporaria = reset_account_password(usuario, actor=current_user)
    except ValueError as exc:
        record_event(action="users.password_reset", entity="user", entity_id=user_id, actor=current_user, success=False, context=audit_request_context())
        return _users_feedback(str(exc))
    record_event(action="users.password_reset", entity="user", entity_id=user_id, actor=current_user, success=True, context=audit_request_context())

    _log.info("Senha redefinida por administrador.")
    if is_htmx_request():
        return render_template(
            "users/_senha_temporaria.html",
            senha_temporaria=senha_temporaria,
            senha_de=usuario.username,
            users=list_users(),
            min_password_length=MIN_PASSWORD_LENGTH,
        )
    return render_template(
        "users/index.html",
        users=list_users(),
        min_password_length=MIN_PASSWORD_LENGTH,
        roles=(ROLE_OPERADOR, ROLE_ADMIN),
        senha_temporaria=senha_temporaria,
        senha_de=usuario.username,
    )


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
        record_event(action="users.set_active", entity="user", entity_id=user_id, actor=current_user, success=False, context=audit_request_context())
        return _users_feedback(str(exc))
    record_event(action="users.set_active", entity="user", entity_id=user_id, actor=current_user, success=True, context={**audit_request_context(), "active": active})
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
        record_event(action="users.set_role", entity="user", entity_id=user_id, actor=current_user, success=False, context=audit_request_context())
        return _users_feedback(str(exc))
    record_event(action="users.set_role", entity="user", entity_id=user_id, actor=current_user, success=True, context={**audit_request_context(), "role": role})
    nome = "administrador" if role == ROLE_ADMIN else "operador"
    return _users_feedback(
        f"Usuário '{usuario.username}' agora é {nome}.", severidade="success"
    )
