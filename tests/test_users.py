"""Contratos de autorização e papel da gestão de contas."""

from __future__ import annotations

import pytest

from app.accounts import service
from app.extensions import login_manager
from app.models import ROLE_ADMIN, ROLE_OPERADOR, User


def _login_as(client, app, user):
    login_manager._user_callback = lambda _user_id: user
    with client.session_transaction() as session:
        session["_user_id"] = "1"
        session["_fresh"] = True


def test_usuario_tem_papeis_explicitos():
    assert User(role=ROLE_ADMIN).is_admin
    assert not User(role=ROLE_OPERADOR).is_admin


def test_gestao_de_usuarios_recusa_operador(app, client):
    operador = User(id=1, username="operador", role=ROLE_OPERADOR, is_active_user=True)
    _login_as(client, app, operador)

    resposta = client.get("/usuarios")

    assert resposta.status_code == 403


def test_gestao_de_usuarios_exige_admin_em_todas_as_operacoes(app, client):
    app.config["WTF_CSRF_ENABLED"] = False
    operador = User(id=1, username="operador", role=ROLE_OPERADOR, is_active_user=True)
    _login_as(client, app, operador)

    for rota in (
        "/usuarios",
        "/usuarios/1/senha",
        "/usuarios/1/ativo",
        "/usuarios/1/papel",
    ):
        resposta = client.post(rota)
        assert resposta.status_code == 403, rota


def test_servico_impede_desativar_propria_conta(monkeypatch):
    administrador = User(id=1, username="admin", role=ROLE_ADMIN, is_active_user=True)
    monkeypatch.setattr(service, "_lock_user_policy", lambda: None)
    monkeypatch.setattr(service.db.session, "refresh", lambda _user: None)

    with pytest.raises(service.UserManagementError, match="própria conta"):
        service.set_active(administrador, False, actor=administrador)
