"""A aplicacao nega por padrao.

Este e o teste que justifica a suite existir. Uma rota que deixa de exigir
sessao continua respondendo 200 e parecendo correta: a falha e silenciosa e so
aparece quando alguem de fora ja entrou.
"""

from __future__ import annotations

import re

import pytest

from app import PUBLIC_ENDPOINTS
from app.web.auth import _safe_next_url

#: Substitui `<int:id>`, `<path:filename>` e afins por um valor navegavel.
_PARAMETRO = re.compile(r"<(?:(?P<tipo>[^:<>]+):)?[^<>]+>")


def _url_plausivel(regra) -> str:
    """URL concreta para uma rota, com ou sem parametro.

    Rotas com parametro ja foram puladas aqui, com o argumento de que "as sem
    parametro ja cobrem a decisao, que e do `before_request` e nao da rota".
    O argumento tinha um furo: a unica rota parametrizada nao publica do app
    era `sharedauth_ui.static`, servindo o CSS e o JS que a propria tela de
    login carrega. Ela estava barrada, o navegador recusava o HTML do
    redirecionamento por MIME, e a suite passava verde -- porque a rota com o
    defeito era exatamente a que o filtro descartava.
    """

    def valor(m: re.Match[str]) -> str:
        return "1" if (m.group("tipo") or "") in ("int", "float") else "x"

    return _PARAMETRO.sub(valor, regra.rule)


def _rotas_get_registradas(app):
    """Toda rota GET da aplicacao, exceto as declaradas publicas."""
    for regra in app.url_map.iter_rules():
        if regra.endpoint in PUBLIC_ENDPOINTS:
            continue
        if "GET" not in (regra.methods or set()):
            continue
        yield _url_plausivel(regra)


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
    assert frozenset(
        {
            "web.login",
            "static",
            "health",
            # CSS e JS do componente de aviso, carregados por `base.html` --
            # que `auth/login.html` estende. Sem esta entrada os dois sao
            # pedidos sem sessao, o gate os manda para /login e o navegador
            # recusa o HTML por MIME: o toast de "Sessao encerrada" some
            # depois do logout, porque quem o monta e o JS bloqueado.
            "sharedauth_ui.static",
        }
    ) == PUBLIC_ENDPOINTS


def test_htmx_sem_sessao_recebe_redirect_de_pagina_inteira(client):
    resposta = client.get("/", headers={"HX-Request": "true"})
    assert resposta.status_code == 401
    assert resposta.headers.get("HX-Redirect", "").endswith("/login")


@pytest.mark.parametrize(
    "destino",
    [
        "https://exemplo.invalido",
        "//exemplo.invalido",
        r"/\exemplo.invalido",
        "/%5cexemplo.invalido",
        "/%255cexemplo.invalido",
        "/%2f%2fexemplo.invalido",
        "/%252f%252fexemplo.invalido",
    ],
)
def test_next_externo_ou_normalizavel_nao_e_aceito(app, destino):
    # Barras invertidas e suas formas percent-encoded podem ser normalizadas
    # pelos navegadores para um URL com host externo.
    with app.test_request_context("/login", query_string={"next": destino}):
        assert _safe_next_url() is None


def test_next_interno_e_preservado(app):
    with app.test_request_context("/login", query_string={"next": "/apostas?periodo=recente"}):
        assert _safe_next_url() == "/apostas?periodo=recente"
