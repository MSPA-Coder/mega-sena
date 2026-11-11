"""A Content-Security-Policy e os cabecalhos defensivos chegam ao cliente.

Este arquivo existe com o mesmo nome nos quatro projetos do mantenedor. Uma
politica que afrouxa nao quebra nada visivelmente -- a pagina continua
carregando --, entao so um teste percebe.
"""

from __future__ import annotations

import pytest

CABECALHOS_ESPERADOS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
}


@pytest.mark.parametrize(("cabecalho", "valor"), sorted(CABECALHOS_ESPERADOS.items()))
def test_cabecalho_defensivo_presente(client, cabecalho, valor):
    resposta = client.get("/login")
    assert resposta.headers.get(cabecalho) == valor


def test_permissions_policy_restringe_dispositivos(client):
    politica = client.get("/login").headers.get("Permissions-Policy", "")
    for recurso in ("camera=()", "microphone=()", "geolocation=()"):
        assert recurso in politica


def test_csp_presente_e_fechada_na_propria_origem(client):
    csp = client.get("/login").headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


def test_csp_nao_admite_inline_nem_origem_externa(client):
    csp = client.get("/login").headers.get("Content-Security-Policy", "")
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp
    # Nenhuma origem externa: fontes e bibliotecas sao servidas pela aplicacao.
    assert "http://" not in csp
    assert "https://" not in csp


def test_pagina_publica_e_pagina_autenticada_nao_ficam_em_cache(client):
    from app.extensions import login_manager
    from app.models import ROLE_OPERADOR, User

    assert client.get("/login").headers.get("Cache-Control") == "no-store"

    operador = User(id=1, username="operador", role=ROLE_OPERADOR, is_active_user=True)
    login_manager._user_callback = lambda _user_id: operador
    with client.session_transaction() as sessao:
        sessao["_user_id"] = "1"
        sessao["_fresh"] = True
    resposta = client.get("/usuarios")
    assert resposta.status_code == 403
    assert resposta.headers.get("Cache-Control") == "no-store"


def test_estatico_mantem_o_cache_proprio(client):
    resposta = client.get("/static/favicon.svg")
    assert resposta.status_code == 200
    assert resposta.headers.get("Cache-Control") != "no-store"
