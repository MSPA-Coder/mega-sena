"""Senha redefinida por administrador vale ate o primeiro acesso.

Quando um administrador redefine a senha de alguem, essa senha passa a ser
conhecida por duas pessoas. A obrigacao de trocar existe para encurtar essa
janela -- e so vale se for verificada em TODA requisicao. Aplicar o desvio
apenas no login e a falha silenciosa que este arquivo mede: a marca fica
ligada, a tela some da frente, e a pessoa segue usando a senha que o
administrador conhece.

A suite nao toca o banco (ver `conftest.py`); as chamadas de servico tem o
`commit` substituido, e o carregamento de usuario e trocado por um objeto em
memoria -- mesma tecnica de `test_autorizacao_por_papel.py`.
"""

from __future__ import annotations

import pytest
from sharedauth.session import marca_de_sessao

from app import PUBLIC_ENDPOINTS
from app.accounts import service
from app.extensions import db, login_manager
from app.models import ROLE_ADMIN, ROLE_OPERADOR, User


def _login_as(client, user):
    login_manager._user_callback = lambda _user_id: user
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True


def _sem_banco(monkeypatch):
    monkeypatch.setattr(service.db.session, "commit", lambda: None)


def _usuario(**kwargs) -> User:
    padrao = {
        "id": 1,
        "username": "fulano",
        "role": ROLE_OPERADOR,
        "is_active_user": True,
        "must_change_password": False,
    }
    padrao.update(kwargs)
    return User(**padrao)


# --- o portao ------------------------------------------------------------


def test_marca_ligada_desvia_qualquer_rota_para_a_troca(app, client):
    usuario = User(
        id=1, username="fulano", role=ROLE_OPERADOR, is_active_user=True,
        must_change_password=True,
    )
    _login_as(client, usuario)

    resposta = client.get("/dashboard", follow_redirects=False)

    assert resposta.status_code == 302
    assert resposta.headers["Location"] == "/minha-senha"


def test_marca_desligada_nao_atrapalha(app, client):
    # Rota sintetica de proposito: toda rota real protegida deste app consulta
    # o banco, e esta suite nao tem banco (ver `conftest.py`). Com o desvio no
    # caminho isso nao aparece -- o portao responde antes da view --, mas o
    # caso "deixa passar" precisa chegar ate a view para provar alguma coisa.
    # Aqui a decisao do portao e a unica variavel.
    app.add_url_rule("/rota-sintetica", "web.rota_sintetica", lambda: "chegou")
    usuario = User(
        id=1, username="fulano", role=ROLE_OPERADOR, is_active_user=True,
        must_change_password=False,
    )
    _login_as(client, usuario)

    resposta = client.get("/rota-sintetica")

    assert resposta.status_code == 200
    assert resposta.get_data(as_text=True) == "chegou"


def test_a_tela_de_troca_nao_entra_em_laco(app, client):
    # A tela que existe para sair da situacao nao pode redirecionar para si
    # mesma. `sharedauth.access` isenta `endpoint_troca` automaticamente.
    usuario = User(
        id=1, username="fulano", role=ROLE_OPERADOR, is_active_user=True,
        must_change_password=True,
    )
    _login_as(client, usuario)

    assert client.get("/minha-senha").status_code == 200


def test_logout_funciona_de_dentro_da_trava(app, client):
    # Sem isto a pessoa fica presa dentro do aplicativo: todo destino devolve
    # para a tela de troca, inclusive a saida.
    app.config["WTF_CSRF_ENABLED"] = False
    usuario = User(
        id=1, username="fulano", role=ROLE_OPERADOR, is_active_user=True,
        must_change_password=True,
    )
    _login_as(client, usuario)

    resposta = client.post("/logout", follow_redirects=False)

    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


@pytest.mark.parametrize(
    "rota",
    [
        "/static/style.css",
        "/sharedauth/sharedauth-ui.css",
        "/health",
    ],
)
def test_estaticos_e_saude_ficam_isentos(app, client, rota):
    # Sem os estaticos a tela de troca chega sem CSS e sem o componente de
    # aviso; sem `/health` o contêiner passaria a ser reportado como doente
    # justamente para quem esta com a senha vencida.
    usuario = User(
        id=1, username="fulano", role=ROLE_OPERADOR, is_active_user=True,
        must_change_password=True,
    )
    _login_as(client, usuario)

    resposta = client.get(rota)

    assert resposta.status_code != 302, f"{rota} foi desviada para a troca"


def test_htmx_com_marca_ligada_recebe_hx_redirect(app, client):
    # Uma troca de fragmento nao pode devolver a tela de troca dentro de um
    # pedaco de pagina -- mesmo motivo do `usar_hx_redirect` do login.
    usuario = User(
        id=1, username="fulano", role=ROLE_OPERADOR, is_active_user=True,
        must_change_password=True,
    )
    _login_as(client, usuario)

    resposta = client.get("/dashboard", headers={"HX-Request": "true"})

    assert resposta.status_code == 403
    assert resposta.headers["HX-Redirect"] == "/minha-senha"


def test_anonimo_continua_indo_para_o_login(app, client):
    # O portao da troca nao pode roubar o caso do anonimo: quem nao entrou nao
    # tem senha a trocar.
    resposta = client.get("/dashboard", follow_redirects=False)

    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_a_tela_de_troca_nao_e_publica(app):
    # Ela exige sessao como qualquer outra: trocar a senha de alguem sem estar
    # logado como essa pessoa seria a falha que o fluxo inteiro evita.
    assert "web.change_password" not in PUBLIC_ENDPOINTS


# --- servico: redefinicao pelo administrador -----------------------------


def test_redefinir_gera_senha_temporaria_e_liga_a_marca(monkeypatch):
    _sem_banco(monkeypatch)
    administrador = User(id=1, username="admin", role=ROLE_ADMIN, is_active_user=True)
    alvo = User(id=2, username="fulano", role=ROLE_OPERADOR, is_active_user=True)
    alvo.set_password("senha-antiga")

    senha = service.reset_password(alvo, actor=administrador)

    assert alvo.must_change_password is True
    assert alvo.check_password(senha) is True
    assert alvo.check_password("senha-antiga") is False


def test_redefinir_nao_repete_a_senha_entre_chamadas(monkeypatch):
    _sem_banco(monkeypatch)
    administrador = User(id=1, username="admin", role=ROLE_ADMIN, is_active_user=True)
    alvo = User(id=2, username="fulano", role=ROLE_OPERADOR, is_active_user=True)
    alvo.set_password("senha-antiga")

    primeira = service.reset_password(alvo, actor=administrador)
    segunda = service.reset_password(alvo, actor=administrador)

    assert primeira != segunda


def test_redefinir_continua_exigindo_administrador(monkeypatch):
    _sem_banco(monkeypatch)
    operador = User(id=1, username="operador", role=ROLE_OPERADOR, is_active_user=True)
    alvo = User(id=2, username="fulano", role=ROLE_OPERADOR, is_active_user=True)

    with pytest.raises(service.UserManagementError):
        service.reset_password(alvo, actor=operador)


def test_a_senha_temporaria_nunca_e_guardada_em_texto_claro(monkeypatch):
    # O hash e a unica forma persistida. Se um dia alguem guardar o valor numa
    # coluna "para facilitar", este teste reprova.
    _sem_banco(monkeypatch)
    administrador = User(id=1, username="admin", role=ROLE_ADMIN, is_active_user=True)
    alvo = User(id=2, username="fulano", role=ROLE_OPERADOR, is_active_user=True)

    senha = service.reset_password(alvo, actor=administrador)

    valores = [
        str(valor)
        for chave, valor in vars(alvo).items()
        if not chave.startswith("_")
    ]
    assert senha not in valores


# --- servico: criacao de conta e bootstrap por CLI -----------------------


def test_conta_nova_nasce_com_a_marca_ligada(monkeypatch):
    # Conta nova tem senha que quem administra escolheu e conhece: e o mesmo
    # caso da redefinicao.
    _sem_banco(monkeypatch)
    monkeypatch.setattr(service, "_lock_user_policy", lambda: None)
    monkeypatch.setattr(service.db.session, "refresh", lambda _user: None)
    monkeypatch.setattr(service.db.session, "add", lambda _user: None)
    monkeypatch.setattr(service.db.session, "scalar", lambda _stmt: None)
    administrador = User(id=1, username="admin", role=ROLE_ADMIN, is_active_user=True)

    novo = service.create_user("fulano", "senha-boa-123", actor=administrador)

    assert novo.must_change_password is True


def test_bootstrap_por_cli_nao_liga_a_marca(monkeypatch):
    # Quem roda o comando tem shell no contêiner e escolheu a propria senha:
    # nao existe o terceiro que a redefinicao pela tela pressupoe.
    _sem_banco(monkeypatch)
    monkeypatch.setattr(service, "_lock_user_policy", lambda: None)
    monkeypatch.setattr(service.db.session, "add", lambda _user: None)
    monkeypatch.setattr(service.db.session, "scalar", lambda _stmt: None)

    novo = service.provision_cli_user("admin", "senha-boa-123", role=ROLE_ADMIN)

    # `is not True`, e nao `is False`: o `default=False` da coluna e aplicado
    # pelo SQLAlchemy no flush, e esta suite substitui o commit -- em memoria o
    # atributo ainda e `None`. O que se mede aqui e que o caminho da CLI nao
    # LIGA a obrigacao; a segunda assercao cobre o outro lado, que o padrao da
    # coluna e desligado (e por isso a linha chega ao banco com `false`).
    assert novo.must_change_password is not True
    assert User.__table__.c.must_change_password.default.arg is False


# --- servico: troca feita pelo dono --------------------------------------


def test_troca_do_dono_desliga_a_marca(monkeypatch):
    _sem_banco(monkeypatch)
    usuario = User(id=1, username="fulano", role=ROLE_OPERADOR, is_active_user=True)
    usuario.set_password("senha-temporaria")
    usuario.must_change_password = True

    service.change_own_password(usuario, "senha-temporaria", "minha-senha-1", "minha-senha-1")

    assert usuario.must_change_password is False
    assert usuario.check_password("minha-senha-1") is True


def test_troca_sem_a_senha_atual_correta_e_recusada(monkeypatch):
    # Sem esta conferencia, uma sessao sequestrada vira tomada de conta.
    _sem_banco(monkeypatch)
    usuario = User(id=1, username="fulano", role=ROLE_OPERADOR, is_active_user=True)
    usuario.set_password("senha-temporaria")
    usuario.must_change_password = True

    with pytest.raises(ValueError):
        service.change_own_password(usuario, "chute", "minha-senha-1", "minha-senha-1")

    assert usuario.must_change_password is True
    assert usuario.check_password("senha-temporaria") is True


def test_redigitar_a_senha_temporaria_nao_conclui_a_troca(monkeypatch):
    # O caso que esvaziaria a obrigacao: a marca se apagaria e a senha que o
    # administrador conhece continuaria valendo.
    _sem_banco(monkeypatch)
    usuario = User(id=1, username="fulano", role=ROLE_OPERADOR, is_active_user=True)
    usuario.set_password("senha-temporaria")
    usuario.must_change_password = True

    with pytest.raises(ValueError):
        service.change_own_password(
            usuario, "senha-temporaria", "senha-temporaria", "senha-temporaria"
        )

    assert usuario.must_change_password is True


# --- a tela de troca -----------------------------------------------------


def test_troca_pela_tela_redireciona_e_libera(app, client, monkeypatch):
    app.config["WTF_CSRF_ENABLED"] = False
    _sem_banco(monkeypatch)
    usuario = User(
        id=1, username="fulano", role=ROLE_OPERADOR, is_active_user=True,
        must_change_password=True,
    )
    usuario.set_password("senha-temporaria")
    _login_as(client, usuario)

    resposta = client.post(
        "/minha-senha",
        data={
            "current_password": "senha-temporaria",
            "new_password": "minha-senha-1",
            "password_confirm": "minha-senha-1",
        },
        follow_redirects=False,
    )

    assert resposta.status_code == 302
    assert usuario.must_change_password is False


def test_troca_recusada_responde_400_e_mantem_a_marca(app, client, monkeypatch):
    app.config["WTF_CSRF_ENABLED"] = False
    _sem_banco(monkeypatch)
    usuario = User(
        id=1, username="fulano", role=ROLE_OPERADOR, is_active_user=True,
        must_change_password=True,
    )
    usuario.set_password("senha-temporaria")
    _login_as(client, usuario)

    resposta = client.post(
        "/minha-senha",
        data={
            "current_password": "chute-errado",
            "new_password": "minha-senha-1",
            "password_confirm": "minha-senha-1",
        },
    )

    assert resposta.status_code == 400
    assert usuario.must_change_password is True


# --- a sessao deixa de valer quando a senha muda -------------------------


def test_a_marca_da_senha_entra_no_identificador_de_sessao(app):
    # O Flask-Login guarda o que `get_id()` devolve. So o id nao bastava:
    # trocar a senha nao derrubava sessao aberta em outro lugar.
    usuario = _usuario()
    usuario.set_password("senha-de-teste")

    with app.app_context():
        identificador = usuario.get_id()

    assert identificador.startswith("1:")
    assert len(identificador.split(":", 1)[1]) == 32


def test_o_identificador_muda_quando_a_senha_muda(app):
    usuario = _usuario()
    usuario.set_password("senha-antiga-1")

    with app.app_context():
        antes = usuario.get_id()
        usuario.set_password("senha-nova-123")
        depois = usuario.get_id()

    assert antes != depois


def test_sessao_com_a_marca_antiga_e_recusada(app, client, monkeypatch):
    # O caso que a mudanca existe para resolver: alguem entrou com a senha
    # antiga, o dono trocou, e a sessao daquele alguem tem de cair.
    usuario = _usuario()
    usuario.set_password("senha-antiga-1")
    with app.app_context():
        identificador_antigo = usuario.get_id()

    monkeypatch.setattr(db.session, "get", lambda _modelo, _id: usuario)
    usuario.set_password("senha-nova-123")

    with client.session_transaction() as sessao:
        sessao["_user_id"] = identificador_antigo
        sessao["_fresh"] = True

    resposta = client.get("/dashboard", follow_redirects=False)

    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_sessao_com_a_marca_atual_continua_valendo(app, client, monkeypatch):
    app.add_url_rule("/rota-sintetica", "web.rota_sintetica", lambda: "chegou")
    usuario = _usuario()
    usuario.set_password("senha-de-teste")
    with app.app_context():
        identificador = usuario.get_id()

    monkeypatch.setattr(db.session, "get", lambda _modelo, _id: usuario)
    with client.session_transaction() as sessao:
        sessao["_user_id"] = identificador
        sessao["_fresh"] = True

    assert client.get("/rota-sintetica").status_code == 200


def test_identificador_no_formato_antigo_e_recusado(app, client, monkeypatch):
    # Sessao de antes desta mudanca, que guardava so o id. Cair uma vez, no
    # primeiro acesso depois do deploy, e o comportamento desejado.
    usuario = _usuario()
    usuario.set_password("senha-de-teste")
    monkeypatch.setattr(db.session, "get", lambda _modelo, _id: usuario)

    with client.session_transaction() as sessao:
        sessao["_user_id"] = "1"
        sessao["_fresh"] = True

    resposta = client.get("/dashboard", follow_redirects=False)

    assert "/login" in resposta.headers["Location"]


def test_trocar_a_propria_senha_nao_derruba_quem_trocou(app, client, monkeypatch):
    # O efeito que se quer e derrubar as OUTRAS sessoes, nao esta. Sem renovar
    # o identificador, a pessoa seria deslogada pela propria troca.
    app.config["WTF_CSRF_ENABLED"] = False
    _sem_banco(monkeypatch)
    usuario = _usuario()
    usuario.set_password("senha-antiga-1")
    with app.app_context():
        identificador = usuario.get_id()

    monkeypatch.setattr(db.session, "get", lambda _modelo, _id: usuario)
    with client.session_transaction() as sessao:
        sessao["_user_id"] = identificador
        sessao["_fresh"] = True

    resposta = client.post(
        "/minha-senha",
        data={
            "current_password": "senha-antiga-1",
            "new_password": "minha-senha-1",
            "password_confirm": "minha-senha-1",
        },
        follow_redirects=False,
    )

    assert resposta.status_code == 302
    with client.session_transaction() as sessao:
        assert sessao["_user_id"] != identificador
        assert sessao["_user_id"].endswith(
            marca_de_sessao(usuario.password_hash, chave_secreta=app.secret_key)
        )
