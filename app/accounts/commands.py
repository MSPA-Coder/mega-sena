"""Alterações de conta e seu evento de sucesso formam uma única transação.

As políticas continuam no serviço, inclusive o lock do último administrador.
Nenhuma senha é enviada ao contexto da auditoria.
"""

from ..audit.contracts import AuditContext
from ..audit.service import add_success
from ..extensions import db
from ..models import ROLE_OPERADOR, User
from . import service


def create_user(
    username: str, password: str, *, role: str = ROLE_OPERADOR, actor: User, audit: AuditContext
) -> User:
    try:
        user = service.create_user(username, password, role=role, actor=actor, commit=False)
        add_success(
            audit,
            action="users.create",
            entity="user",
            entity_id=user.id,
            details={"username": user.username, "role": user.role},
        )
        db.session.commit()
        return user
    except Exception:
        db.session.rollback()
        raise


def provision_cli_user(username: str, password: str, *, role: str | None = None) -> User:
    try:
        user = service.provision_cli_user(username, password, role=role, commit=False)
        db.session.flush()
        add_success(
            AuditContext(context={"source": "cli"}),
            action="users.provision",
            entity="user",
            entity_id=user.id,
        )
        db.session.commit()
        return user
    except Exception:
        db.session.rollback()
        raise


def reset_password(user: User, *, actor: User, audit: AuditContext) -> str:
    try:
        password = service.reset_password(user, actor=actor, commit=False)
        add_success(audit, action="users.password_reset", entity="user", entity_id=user.id)
        db.session.commit()
        return password
    except Exception:
        db.session.rollback()
        raise


def change_own_password(
    user: User, current: str, new: str, confirmation: str, *, audit: AuditContext
) -> None:
    try:
        service.change_own_password(user, current, new, confirmation, commit=False)
        add_success(audit, action="users.change_own_password", entity="user", entity_id=user.id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def set_active(user: User, active: bool, *, actor: User, audit: AuditContext) -> None:
    try:
        service.set_active(user, active, actor=actor, commit=False)
        add_success(
            audit,
            action="users.set_active",
            entity="user",
            entity_id=user.id,
            details={"active": active},
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def set_role(user: User, role: str, *, actor: User, audit: AuditContext) -> None:
    try:
        service.set_role(user, role, actor=actor, commit=False)
        add_success(
            audit, action="users.set_role", entity="user", entity_id=user.id, details={"role": role}
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
