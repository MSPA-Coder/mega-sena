"""O logout invalida o cookie de sessão emitido, não só o apaga no navegador."""

import re

import pytest

from app.extensions import db
from app.models import AuditEvent, User

pytestmark = pytest.mark.banco

SENHA = "Synthetic-password-20261021"
NOME = "qa_http_logout"


def _csrf(response):
    return re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    ).group(1)


def test_copia_do_cookie_deixa_de_valer_depois_do_logout(app_com_banco):
    with app_com_banco.app_context():
        usuario = User(username=NOME, role="admin")
        usuario.set_password(SENHA)
        db.session.add(usuario)
        db.session.commit()
        user_id = usuario.id
    try:
        original = app_com_banco.test_client()
        original.post(
            "/login",
            data={
                "username": NOME,
                "password": SENHA,
                "csrf_token": _csrf(original.get("/login")),
            },
        )
        assert original.get("/dashboard").status_code == 200

        copia = app_com_banco.test_client()
        for cookie in original._cookies.values():
            copia.set_cookie(cookie.key, cookie.value, domain="localhost")
        assert copia.get("/dashboard").status_code == 200

        saida = original.post("/logout", data={"csrf_token": _csrf(original.get("/dashboard"))})
        assert saida.status_code == 302

        assert copia.get("/dashboard").status_code == 302
        assert "/login" in copia.get("/dashboard").headers["Location"]
    finally:
        with app_com_banco.app_context():
            AuditEvent.query.filter_by(actor_user_id=user_id).delete()
            db.session.delete(db.session.get(User, user_id))
            db.session.commit()


def test_logout_funciona_de_dentro_da_trava_de_troca_de_senha(app_com_banco):
    # Sem isto a pessoa fica presa dentro do aplicativo: todo destino devolve
    # para a tela de troca, inclusive a saida.
    with app_com_banco.app_context():
        usuario = User(username=NOME + "_trava", role="operador", must_change_password=True)
        usuario.set_password(SENHA)
        db.session.add(usuario)
        db.session.commit()
        user_id = usuario.id
    try:
        client = app_com_banco.test_client()
        client.post(
            "/login",
            data={
                "username": NOME + "_trava",
                "password": SENHA,
                "csrf_token": _csrf(client.get("/login")),
            },
        )
        pagina = client.get("/minha-senha")
        assert pagina.status_code == 200

        resposta = client.post("/logout", data={"csrf_token": _csrf(pagina)})

        assert resposta.status_code == 302
        assert "/login" in resposta.headers["Location"]
    finally:
        with app_com_banco.app_context():
            AuditEvent.query.filter_by(actor_user_id=user_id).delete()
            db.session.delete(db.session.get(User, user_id))
            db.session.commit()
