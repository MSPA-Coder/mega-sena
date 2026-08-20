"""O login tem limite de tentativas.

Regressão: `sharedauth.ratelimit.iniciar_limiter` devolve uma instância nova a
cada `create_app()` (não um singleton de módulo — ver `app/extensions.py`), o
que impede decorar `/login` no import de `auth.py` como antes. A aplicação do
limite virou uma chamada em `app/__init__.py`, depois que a rota já está
registrada: `limiter.limit(...)(app.view_functions["web.login"])` devolve uma
função *nova*, embrulhada -- descartar esse retorno em vez de reatribuir a
`app.view_functions["web.login"]` deixa o limite decorado e nunca aplicado, e
toda requisição chama a view original, sem limite nenhum. Reproduzido de fato
antes desta correção: 11 requisições seguidas devolviam 200.
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
