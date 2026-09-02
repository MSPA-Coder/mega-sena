"""O login tem limite de tentativas.

`sharedauth.ratelimit.iniciar_limiter` devolve uma instancia por aplicacao, e
o limite e aplicado depois do registro da rota em `app/__init__.py`.
`limiter.limit(...)(app.view_functions["web.login"])` devolve uma nova funcao;
ela precisa permanecer atribuida a `app.view_functions["web.login"]` para que
as requisicoes passem pelo limitador.
"""

from __future__ import annotations

from sharedauth.ratelimit import LIMITE_LOGIN_PADRAO

from app.extensions import login_manager
from app.models import ROLE_ADMIN, User
from app.web import bets

_GENERATION_DEFAULTS = {
    "bet_quantity": 6,
    "generation_amount": 5,
    "consecutive_count": None,
    "even_min": None,
    "even_max": None,
    "sum_min": None,
    "sum_max": None,
    "range_min_occupied": None,
    "range_max_per_band": None,
}


def _login_as(client, user) -> None:
    """Mesma técnica de tests/test_users.py: sessão sem tocar o banco."""
    login_manager._user_callback = lambda _user_id: user
    with client.session_transaction() as session:
        session["_user_id"] = "1"
        session["_fresh"] = True


def test_limite_de_login_e_dez_por_minuto() -> None:
    assert LIMITE_LOGIN_PADRAO == "10 per minute"


def test_login_bloqueia_apos_o_limite(client) -> None:
    for _ in range(10):
        resposta = client.get("/login")
        assert resposta.status_code == 200
    resposta = client.get("/login")
    assert resposta.status_code == 429


def test_rationale_bloqueia_apos_o_limite_dedicado(client, monkeypatch) -> None:
    """MS-03: `/rationale` é uma das três rotas caras sem teto antes desta
    correção -- limite dedicado de 10/min, mais estreito que o global.

    O cálculo combinatório em si é puro, mas `_read_generation_state` lê os
    padrões de geração salvos (`get_generation_defaults`, que consulta o
    banco) -- mesma técnica de mock de tests/test_bet_generation_routes.py
    para exercitar a rota sem PostgreSQL.
    """
    monkeypatch.setattr(bets, "get_generation_defaults", lambda: dict(_GENERATION_DEFAULTS))
    _login_as(client, User(id=1, username="admin", role=ROLE_ADMIN, is_active_user=True))

    for _ in range(10):
        resposta = client.get("/rationale")
        assert resposta.status_code == 200
    resposta = client.get("/rationale")
    assert resposta.status_code == 429


def test_rationale_dentro_do_limite_nao_e_afetada_pelo_padrao_global(client, monkeypatch) -> None:
    """O limite dedicado (mais estreito) é o que vale, não o global de 60/min."""
    monkeypatch.setattr(bets, "get_generation_defaults", lambda: dict(_GENERATION_DEFAULTS))
    _login_as(client, User(id=1, username="admin", role=ROLE_ADMIN, is_active_user=True))

    for _ in range(5):
        assert client.get("/rationale").status_code == 200
