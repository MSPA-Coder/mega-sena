"""Estrutura do menu do topo: grupos, quem vê o quê e qual item acende.

O menu tem três grupos (Apostas, Concursos e Conta e administração) além do
Dashboard solto. O que pode quebrar sem ninguém notar: um grupo "só
administrador" que esconde Preferências e Minha senha de quem não é admin, um
item que acende em tela que não é dele (`/contests` é prefixo de
`/contests/importar`) e um submenu sem o botão que o abre. As páginas usadas
aqui não consultam o banco, então a camada sem banco basta; as telas que
dependem de dados estão em `test_minhas_apostas_http.py`.
"""

from __future__ import annotations

from html.parser import HTMLParser

from app.extensions import login_manager
from app.models import ROLE_ADMIN, ROLE_OPERADOR, User


class _LerMenu(HTMLParser):
    """Lê `#primary-nav`: links soltos e grupos com os seus subitens."""

    def __init__(self) -> None:
        super().__init__()
        self.soltos: list[tuple[str, bool]] = []
        self.grupos: dict[str, dict] = {}
        self._na_barra = False
        self._grupo: dict | None = None
        self._coleta: tuple | str | None = None
        self._texto = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if tag == "nav" and a.get("id") == "primary-nav":
            self._na_barra = True
        if not self._na_barra:
            return
        if tag == "div" and "nav-group" in classes:
            self._grupo = {"ativo": "active" in classes, "itens": [], "controla": None}
        elif tag == "button" and "nav-group-toggle" in classes:
            self._coleta, self._texto = "grupo", ""
            self._grupo["controla"] = a.get("aria-controls")
            self._grupo["fechado"] = a.get("aria-expanded") == "false"
        elif tag == "a":
            self._coleta, self._texto = ("link", "active" in classes, a.get("aria-current")), ""
        elif tag == "form":
            self._grupo = None

    def handle_data(self, data):
        if self._coleta:
            self._texto += data

    def handle_endtag(self, tag):
        if tag == "button" and self._coleta == "grupo":
            self.grupos[self._texto.strip()] = self._grupo
            self._coleta = None
        elif tag == "a" and isinstance(self._coleta, tuple):
            _, ativo, corrente = self._coleta
            destino = self._grupo["itens"] if self._grupo else self.soltos
            destino.append((self._texto.strip(), ativo, corrente == "page"))
            self._coleta = None
        elif tag == "nav":
            self._na_barra = False


def _menu(monkeypatch, client, usuario, caminho):
    # `monkeypatch` desfaz o login falso ao fim do teste: sem isso ele vaza para
    # os testes seguintes, que passariam a rodar como um usuário que não existe.
    monkeypatch.setattr(login_manager, "_user_callback", lambda _user_id: usuario)
    with client.session_transaction() as sessao:
        sessao["_user_id"] = "1"
        sessao["_fresh"] = True
    resposta = client.get(caminho)
    assert resposta.status_code == 200, caminho
    html = resposta.get_data(as_text=True)
    leitor = _LerMenu()
    leitor.feed(html)
    return leitor, html


def _rotulos(itens):
    return [rotulo for rotulo, *_ in itens]


def _administrador():
    return User(id=1, username="admin", role=ROLE_ADMIN, is_active_user=True)


def _operador():
    return User(id=1, username="operador", role=ROLE_OPERADOR, is_active_user=True)


def test_administrador_ve_os_tres_grupos_na_ordem_combinada(monkeypatch, client):
    menu, html = _menu(monkeypatch, client, _administrador(), "/preferencias")

    assert _rotulos(menu.soltos) == ["Dashboard"]
    assert list(menu.grupos) == ["Apostas", "Concursos", "Conta e administração"]
    assert _rotulos(menu.grupos["Apostas"]["itens"]) == ["Gerar apostas", "Minhas apostas"]
    assert _rotulos(menu.grupos["Concursos"]["itens"]) == ["Resultados", "Importar resultados"]
    assert _rotulos(menu.grupos["Conta e administração"]["itens"]) == [
        "Configurações",
        "Preferências",
        "Usuários",
        "Minha senha",
    ]
    # Todo botão de grupo nasce fechado e aponta para um painel que existe.
    for grupo in menu.grupos.values():
        assert grupo["fechado"]
        assert f'id="{grupo["controla"]}"' in html


def test_operador_nao_perde_preferencias_nem_minha_senha(monkeypatch, client):
    """O grupo é de todos: só Configurações e Usuários dependem do papel."""
    menu, _html = _menu(monkeypatch, client, _operador(), "/preferencias")

    assert list(menu.grupos) == ["Apostas", "Concursos", "Conta e administração"]
    assert _rotulos(menu.grupos["Conta e administração"]["itens"]) == [
        "Preferências",
        "Minha senha",
    ]


def test_grupo_conta_acende_so_na_tela_aberta(monkeypatch, client):
    menu, _html = _menu(monkeypatch, client, _administrador(), "/preferencias")

    conta = menu.grupos["Conta e administração"]
    assert conta["ativo"]
    assert {r: c for r, _a, c in conta["itens"]} == {
        "Configurações": False,
        "Preferências": True,
        "Usuários": False,
        "Minha senha": False,
    }
    assert not menu.grupos["Apostas"]["ativo"]
    assert not menu.grupos["Concursos"]["ativo"]


def test_importar_resultados_acende_o_grupo_sem_acender_resultados(monkeypatch, client):
    """`/contests` é prefixo de `/contests/importar`; quem decide é o endpoint."""
    menu, html = _menu(monkeypatch, client, _operador(), "/contests/importar")

    concursos = menu.grupos["Concursos"]
    assert concursos["ativo"]
    assert {r: c for r, _a, c in concursos["itens"]} == {
        "Resultados": False,
        "Importar resultados": True,
    }
    assert not menu.grupos["Apostas"]["ativo"]
    # A importação mora aqui, e só aqui: planilha e link.
    assert 'action="/contests/import"' in html
    assert 'action="/contests/import-link"' in html
