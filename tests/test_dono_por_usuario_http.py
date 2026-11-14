"""Apostas, padrões de geração e tema de cada conta (ADR 0004), pela porta pública.

Decisão de 04/11/2026, para quando houver mais de uma conta. Cada conta vê só as
próprias apostas, gera com os próprios padrões e leva o próprio tema; o
endereço da planilha e a reinicialização da base continuam de administrador.
"""

from __future__ import annotations

import re
from uuid import uuid4

import pytest

from app.extensions import db
from app.models import AuditEvent, GeneratedBet, User, UserConfig

pytestmark = pytest.mark.banco

SENHA = "Synthetic-password-20261104"
ADMIN, OPERADOR = "qa_dono_admin", "qa_dono_operador"


def _csrf(response):
    return re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    ).group(1)


def _remover_contas(nomes) -> None:
    ids = [u.id for u in User.query.filter(User.username.in_(nomes))]
    if ids:
        GeneratedBet.query.filter(GeneratedBet.owner_id.in_(ids)).delete(synchronize_session=False)
        AuditEvent.query.filter(AuditEvent.actor_user_id.in_(ids)).delete(synchronize_session=False)
        User.query.filter(User.id.in_(ids)).delete(synchronize_session=False)


@pytest.fixture(scope="module")
def contas(app_com_banco):
    """Um admin e um operador logados, um login de cada para o módulo todo."""
    with app_com_banco.app_context():
        _remover_contas([ADMIN, OPERADOR])
        ids = {}
        for nome, papel in ((ADMIN, "admin"), (OPERADOR, "operador")):
            usuario = User(username=nome, role=papel)
            usuario.set_password(SENHA)
            db.session.add(usuario)
            db.session.flush()
            ids[nome] = usuario.id
        db.session.commit()
    clientes = {}
    for nome in (ADMIN, OPERADOR):
        cliente = app_com_banco.test_client()
        # Um IP por cliente: o limite de acessos ao login é por IP e vale para
        # a suíte inteira; sem isto, estes dois logins esgotam a cota dos
        # módulos seguintes (mesma técnica de test_administracao_importacao_http).
        cliente.environ_base["REMOTE_ADDR"] = "2001:db8::" + uuid4().hex[:4] + ":" + uuid4().hex[:4]
        cliente.post(
            "/login",
            data={"username": nome, "password": SENHA, "csrf_token": _csrf(cliente.get("/login"))},
        )
        clientes[nome] = cliente
    yield clientes, ids
    with app_com_banco.app_context():
        db.session.rollback()
        _remover_contas([ADMIN, OPERADOR])
        db.session.commit()


# --- Padrões de geração ------------------------------------------------------


def _quantidade_padrao(html: str) -> str:
    return re.search(r'name="generation_amount"[^>]*value="([^"]*)"', html).group(1)


def test_operador_abre_configuracoes_sem_as_secoes_do_sistema(contas):
    clientes, _ = contas
    html = clientes[OPERADOR].get("/settings").get_data(as_text=True)
    admin = clientes[ADMIN].get("/settings").get_data(as_text=True)

    assert "Meus padrões de geração" in html
    assert "results_source_url" not in html and "Reiniciar base" not in html
    assert "results_source_url" in admin and "Reiniciar base" in admin


def test_padroes_de_geracao_sao_de_cada_conta(app_com_banco, contas):
    clientes, ids = contas
    operador = clientes[OPERADOR]
    resposta = operador.post(
        "/settings",
        data={"csrf_token": _csrf(operador.get("/settings")), "bet_quantity": "6",
              "generation_amount": "9"},
    )

    assert resposta.status_code == 302
    assert _quantidade_padrao(operador.get("/settings").get_data(as_text=True)) == "9"
    assert _quantidade_padrao(clientes[ADMIN].get("/settings").get_data(as_text=True)) != "9"
    with app_com_banco.app_context():
        assert db.session.get(UserConfig, (ids[OPERADOR], "generation_amount")).value == "9"
        assert db.session.get(UserConfig, (ids[ADMIN], "generation_amount")) is None


@pytest.mark.parametrize("rota", ["/settings/sistema", "/reset"])
def test_operador_nao_altera_o_sistema(contas, rota):
    clientes, _ = contas
    operador = clientes[OPERADOR]
    resposta = operador.post(rota, data={"csrf_token": _csrf(operador.get("/settings"))})

    assert resposta.status_code == 403


@pytest.mark.parametrize("digitado", [None, "", "apaga", "SIM"])
def test_reiniciar_base_sem_a_palavra_digitada_nao_apaga_nada(app_com_banco, contas, digitado):
    """O diálogo do navegador não basta: o servidor exige a palavra APAGAR."""
    clientes, ids = contas
    admin = clientes[ADMIN]
    with app_com_banco.app_context():
        # A reinicialização grava um evento de auditoria: sem evento novo, não rodou.
        eventos_antes = AuditEvent.query.filter_by(actor_user_id=ids[ADMIN]).count()
    dados = {"csrf_token": _csrf(admin.get("/settings"))}
    if digitado is not None:
        dados["confirmacao"] = digitado

    resposta = admin.post("/reset", data=dados, headers={"HX-Request": "true"})

    assert "Nada foi apagado" in resposta.get_data(as_text=True)
    with app_com_banco.app_context():
        assert AuditEvent.query.filter_by(actor_user_id=ids[ADMIN]).count() == eventos_antes


# --- Tema --------------------------------------------------------------------


def test_tema_escolhido_vale_na_conta_sem_depender_do_cookie(app_com_banco, contas):
    clientes, ids = contas
    operador = clientes[OPERADOR]
    token = _csrf(operador.get("/settings"))

    assert operador.post("/preferencias/tema", data={"theme": "dark", "csrf_token": token}).status_code == 204
    with app_com_banco.app_context():
        assert db.session.get(User, ids[OPERADOR]).theme == "dark"
    # Outro aparelho: cookie dizendo claro, conta dizendo escuro. Vale a conta.
    operador.set_cookie("theme", "light")
    assert 'data-theme="dark"' in operador.get("/settings").get_data(as_text=True)
    assert 'data-theme="dark"' not in clientes[ADMIN].get("/settings").get_data(as_text=True)


def test_tema_desconhecido_e_recusado(contas):
    clientes, _ = contas
    operador = clientes[OPERADOR]
    token = _csrf(operador.get("/settings"))

    resposta = operador.post("/preferencias/tema", data={"theme": "roxo", "csrf_token": token})

    assert resposta.status_code == 400


def test_sem_escolha_na_conta_vale_o_cookie(contas):
    clientes, _ = contas
    admin = clientes[ADMIN]
    admin.set_cookie("theme", "dark")
    assert 'data-theme="dark"' in admin.get("/settings").get_data(as_text=True)
    admin.delete_cookie("theme")
