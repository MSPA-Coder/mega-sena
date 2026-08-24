"""Camada de serviço para gerenciamento de contas de usuário.

Único ponto de validação de senha: tanto a tela de usuários quanto o comando
`criar-usuario` chamam estas funções, então a política vale igual nos dois
lugares.
"""

from __future__ import annotations

from sharedauth.passwords import MIN_PASSWORD_LENGTH, validar_tamanho  # noqa: F401 (reexportado)
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import ROLE_ADMIN, ROLE_OPERADOR, USER_ROLES, User


class UserManagementError(ValueError):
    """Falha de política ao alterar uma conta."""


def _validate_password(password: str) -> None:
    # `SenhaMuitoCurtaError` é um `ValueError`, então quem já captura
    # `ValueError` aqui (rota, CLI) continua funcionando sem mudança.
    validar_tamanho(password)


def list_users() -> list[User]:
    return list(db.session.scalars(db.select(User).order_by(User.username)))


def create_user(
    username: str, password: str, *, role: str = ROLE_OPERADOR, actor: User
) -> User:
    _require_admin(actor)
    _lock_user_policy()
    db.session.refresh(actor)
    _require_admin(actor)
    username = username.strip()
    if not username:
        raise ValueError("O nome de usuário não pode ser vazio.")
    _validate_password(password)
    _validate_role(role)
    existente = db.session.scalar(db.select(User).where(User.username == username))
    if existente is not None:
        raise UserManagementError(f"Já existe um usuário com o nome '{username}'.")
    usuario = User(username=username, is_active_user=True, role=role)
    usuario.set_password(password)
    db.session.add(usuario)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise UserManagementError("Já existe um usuário com esse nome.") from exc
    return usuario


def provision_cli_user(
    username: str, password: str, *, role: str | None = None
) -> User:
    """Provisiona o acesso confiável da CLI sem abrir um bypass da tela."""
    _lock_user_policy()
    username = username.strip()
    if not username:
        raise UserManagementError("O nome de usuário não pode ser vazio.")
    _validate_password(password)
    existente = db.session.scalar(db.select(User).where(User.username == username))
    if existente is not None:
        existente.set_password(password)
        existente.is_active_user = True
        db.session.commit()
        return existente

    total = db.session.scalar(db.select(func.count(User.id))) or 0
    if total == 0:
        if role == ROLE_OPERADOR:
            raise UserManagementError(
                "O primeiro usuário deve ser administrador."
            )
        role = ROLE_ADMIN
    role = role or ROLE_OPERADOR
    _validate_role(role)
    usuario = User(username=username, is_active_user=True, role=role)
    usuario.set_password(password)
    db.session.add(usuario)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise UserManagementError("Já existe um usuário com esse nome.") from exc
    return usuario


def reset_password(user: User, password: str, *, actor: User) -> None:
    _require_admin(actor)
    _validate_password(password)
    user.set_password(password)
    db.session.commit()


def set_active(user: User, active: bool, *, actor: User) -> None:
    _require_admin(actor)
    _lock_user_policy()
    db.session.refresh(actor)
    db.session.refresh(user)
    _require_admin(actor)
    if not active and user.id == actor.id:
        raise UserManagementError("Você não pode desativar a própria conta.")
    if not active and _is_last_active_user(user):
        raise UserManagementError(
            "Não é possível desativar o único usuário ativo — "
            "isso bloquearia o acesso de todo mundo."
        )
    if not active and user.is_admin and _is_last_active_admin(user):
        raise UserManagementError(
            "Não é possível desativar o único administrador ativo."
        )
    user.is_active_user = active
    db.session.commit()


def set_role(user: User, role: str, *, actor: User) -> None:
    _require_admin(actor)
    _lock_user_policy()
    db.session.refresh(actor)
    db.session.refresh(user)
    _require_admin(actor)
    _validate_role(role)
    if (
        user.role == ROLE_ADMIN
        and role != ROLE_ADMIN
        and (_is_last_admin(user) or _is_last_active_admin(user))
    ):
        raise UserManagementError(
            "Não é possível remover o papel do único administrador ativo."
        )
    user.role = role
    db.session.commit()


def _validate_role(role: str) -> None:
    if role not in USER_ROLES:
        raise UserManagementError("Papel de usuário inválido.")


def _require_admin(actor: User | None) -> None:
    if actor is None or not actor.is_active_user or not actor.is_admin:
        raise UserManagementError("Apenas administradores podem gerir usuários.")


def _lock_user_policy() -> None:
    """Serializa alterações que podem remover o último administrador."""
    db.session.execute(
        db.text("SELECT pg_advisory_xact_lock(hashtext(:policy))"),
        {"policy": "mega-sena-user-policy"},
    )


def _is_last_admin(user: User) -> bool:
    administradores = db.session.scalar(
        db.select(func.count(User.id)).where(User.role == ROLE_ADMIN)
    )
    return bool(administradores == 1)


def _is_last_active_admin(user: User) -> bool:
    if not user.is_active_user or not user.is_admin:
        return False
    outros_ativos = db.session.scalar(
        db.select(func.count(User.id)).where(
            User.role == ROLE_ADMIN,
            User.is_active_user.is_(True),
            User.id != user.id,
        )
    )
    return not outros_ativos


def _is_last_active_user(user: User) -> bool:
    if not user.is_active_user:
        return False
    outros_ativos = db.session.scalar(
        db.select(func.count(User.id)).where(
            User.is_active_user.is_(True), User.id != user.id
        )
    )
    return not outros_ativos
