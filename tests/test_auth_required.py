"""A aplicacao nega por padrao.

Este e o teste que justifica a suite existir. Uma rota que deixa de exigir
sessao continua respondendo 200 e parecendo correta: a falha e silenciosa e so
aparece quando alguem de fora ja entrou.
"""

from __future__ import annotations

import pytest

from app import PUBLIC_ENDPOINTS


def _rotas_get_registradas(app):
    """Toda rota GET da aplicacao, exceto as declaradas publicas."""
    for regra in app.url_map.iter_rules():
        if regra.endpoint in PUBLIC_ENDPOINTS:
            continue
        if "GET" not in (regra.methods or set()):
            continue
        # Rotas com parametro exigiriam um valor plausivel; as sem parametro ja
        # cobrem a decisao, que e do `before_request` e nao da rota.
        if regra.arguments:
            continue
        yield regra.rule


def test_existem_rotas_protegidas_para_verificar(app):
    # Protege o proprio teste: se a coleta parasse de encontrar rotas, os testes
    # abaixo passariam sem exercitar nada.
    assert list(_rotas_get_registradas(app))


def test_rota_protegida_recusa_acesso_anonimo(app, client):
    for rota in _rotas_get_registradas(app):
        resposta = client.get(rota)
        assert resposta.status_code == 302, f"{rota} respondeu {resposta.status_code} sem sessao"
        assert "/login" in resposta.headers.get("Location", "")


def test_login_e_publico(client):
    assert client.get("/login").status_code == 200


def test_lista_de_publicos_e_curta_e_conhecida(app):
    # A lista e de rotas publicas, nao de protegidas: uma rota nova nasce
    # protegida. Este teste existe para que acrescentar algo aqui seja uma
    # decisao consciente, nao um efeito colateral.
    assert frozenset({"web.login", "static"}) == PUBLIC_ENDPOINTS


def test_htmx_sem_sessao_recebe_redirect_de_pagina_inteira(client):
    resposta = client.get("/", headers={"HX-Request": "true"})
    assert resposta.status_code == 401
    assert resposta.headers.get("HX-Redirect", "").endswith("/login")


@pytest.mark.parametrize("destino", ["https://exemplo.invalido", "//exemplo.invalido"])
def test_next_externo_nao_e_aceito(client, destino):
    # Sem esta recusa, a tela de login viraria um redirecionador aberto.
    resposta = client.get(f"/login?next={destino}")
    assert resposta.status_code == 200
