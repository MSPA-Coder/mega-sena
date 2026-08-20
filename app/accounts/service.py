"""Camada de serviço para gerenciamento de contas de usuário.

Único ponto de validação de senha: tanto a tela de usuários quanto o comando
`criar-usuario` chamam estas funções, então a política vale igual nos dois
lugares.
"""

from __future__ import annotations

from sharedauth.passwords import MIN_PASSWORD_LENGTH, validar_tamanho  # noqa: F401 (reexportado)
from sqlalchemy import func

from ..extensions import db
from ..models import User


def _validate_password(password: str) -> None:
    # `SenhaMuitoCurtaError` é um `ValueError`, então quem já captura
    # `ValueError` aqui (rota, CLI) continua funcionando sem mudança.
    validar_tamanho(password)


def list_users() -> list[User]:
    return list(db.session.scalars(db.select(User).order_by(User.username)))


def create_user(username: str, password: str) -> User:
    username = username.strip()
    if not username:
        raise ValueError("O nome de usuário não pode ser vazio.")
    _validate_password(password)
    existente = db.session.scalar(db.select(User).where(User.username == username))
    if existente is not None:
        raise ValueError(f"Já existe um usuário com o nome '{username}'.")
    usuario = User(username=username, is_active_user=True)
    usuario.set_password(password)
    db.session.add(usuario)
    db.session.commit()
    return usuario


def reset_password(user: User, password: str) -> None:
    _validate_password(password)
    user.set_password(password)
    db.session.commit()


def set_active(user: User, active: bool) -> None:
    if not active and _is_last_active_user(user):
        raise ValueError(
            "Não é possível desativar o único usuário ativo — "
            "isso bloquearia o acesso de todo mundo."
        )
    user.is_active_user = active
    db.session.commit()


def _is_last_active_user(user: User) -> bool:
    if not user.is_active_user:
        return False
    outros_ativos = db.session.scalar(
        db.select(func.count(User.id)).where(
            User.is_active_user.is_(True), User.id != user.id
        )
    )
    return not outros_ativos
