"""O login tem limite de tentativas.

`sharedauth.ratelimit.iniciar_limiter` devolve uma instancia por aplicacao, e
o limite e aplicado depois do registro da rota em `app/__init__.py`.
`limiter.limit(...)(app.view_functions["web.login"])` devolve uma nova funcao;
ela precisa permanecer atribuida a `app.view_functions["web.login"]` para que
as requisicoes passem pelo limitador.
"""

from __future__ import annotations

from sharedauth.ratelimit import LIMITE_LOGIN_PADRAO


def test_limite_de_login_e_dez_por_minuto() -> None:
    assert LIMITE_LOGIN_PADRAO == "10 per minute"


def test_login_bloqueia_apos_o_limite(client) -> None:
    for _ in range(10):
        resposta = client.get("/login")
        assert resposta.status_code == 200
    resposta = client.get("/login")
    assert resposta.status_code == 429
