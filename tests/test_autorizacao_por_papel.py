"""O papel decide, e a decisao fica no servidor.

Esconder o item no menu e apresentacao. O que impede um operador de apagar a
base e o `@admin_required` na rota -- e e isso que este arquivo mede, sem
passar pela interface.

Por que o conjunto INTEIRO, e nao uma rota de cada vez: `/reset` apaga todos os
concursos e apostas e ficou sem decorator por tempo indeterminado, enquanto
`/usuarios` tinha o seu. Verificar rota por rota so encontra o que alguem ja
suspeitava; comparar o conjunto encontra tambem a rota que ninguem lembrou de
verificar. Uma rota nova de administrador reprova aqui ate ser declarada, e um
decorator removido por engano reprova pelo outro lado.
"""

from __future__ import annotations

import pytest

from app.web.authorization import PAPEL_ADMIN

#: Endpoints restritos a administradores.
#:
#: Configuracoes entrou junto com Usuarios: `reset_database` apaga TODOS os
#: concursos e apostas, e `save_settings` muda o padrao com que todo mundo gera
#: aposta. O GET de `/settings` tambem, porque um formulario visivel que recusa
#: o proprio POST seria uma tela existindo para nao funcionar.
ENDPOINTS_DE_ADMIN = frozenset(
    {
        "web.settings_page",
        "web.save_settings",
        "web.reset_database",
        "web.users_page",
        "web.create_user",
        "web.reset_user_password",
        "web.toggle_user_active",
        "web.change_user_role",
    }
)


class _UsuarioFalso:
    """Substitui `current_user` sem tocar o banco: o decorator so consulta
    `is_authenticated` e `is_admin`."""

    def __init__(self, *, admin: bool) -> None:
        self.is_authenticated = True
        self.is_admin = admin


def _endpoints_protegidos_por_papel(app) -> set[str]:
    return {
        endpoint
        for endpoint, view in app.view_functions.items()
        if getattr(view, "papel_exigido", None) == PAPEL_ADMIN
    }


def test_conjunto_de_rotas_de_admin_e_exatamente_o_declarado(app):
    assert _endpoints_protegidos_por_papel(app) == ENDPOINTS_DE_ADMIN, (
        "As rotas protegidas por papel divergiram da lista declarada. Se uma "
        "rota nova e mesmo de administrador, acrescente-a aqui; se um "
        "decorator sumiu, devolva-o -- nao ajuste a lista para o teste passar."
    )


def test_existem_rotas_de_admin_para_verificar(app):
    # Protege o proprio teste: sem isto, um erro que zerasse a coleta deixaria
    # a comparacao acima passando por vacuidade.
    assert _endpoints_protegidos_por_papel(app)


@pytest.fixture
def rota_protegida():
    from app.web.authorization import admin_required

    @admin_required
    def view():
        return "alcancou"

    return view


def test_admin_alcanca(app, monkeypatch, rota_protegida):
    monkeypatch.setattr("app.web.authorization.current_user", _UsuarioFalso(admin=True))
    with app.test_request_context("/settings"):
        assert rota_protegida() == "alcancou"


def test_operador_recebe_403(app, monkeypatch, rota_protegida):
    monkeypatch.setattr("app.web.authorization.current_user", _UsuarioFalso(admin=False))
    with app.test_request_context("/reset"), pytest.raises(Exception) as erro:
        rota_protegida()
    # 403, nao redirecionamento para o login: quem chegou aqui ja esta
    # autenticado, e entrar de novo nao daria o papel que falta.
    assert "403" in str(erro.value)


def test_anonimo_sem_a_propriedade_recebe_403(app, monkeypatch, rota_protegida):
    # `current_user.is_authenticated and current_user.is_admin` precisa negar
    # quando `is_admin` nem existe (anonimo do Flask-Login), nao estourar
    # AttributeError e virar 500.
    class _Anonimo:
        is_authenticated = False

    monkeypatch.setattr("app.web.authorization.current_user", _Anonimo())
    with app.test_request_context("/settings"), pytest.raises(Exception) as erro:
        rota_protegida()
    assert "403" in str(erro.value)
