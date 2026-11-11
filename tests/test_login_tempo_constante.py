"""O login paga o hash da senha também para usuário inexistente e inativo.

Se o scrypt só rodasse para conta ativa, o tempo da resposta diria quais nomes
existem, mesmo com a mensagem igual. O teste conta as chamadas ao hash do
Werkzeug pelo POST de verdade, nos três caminhos de recusa e no de sucesso.
"""

import re
from uuid import uuid4

import pytest
import werkzeug.security as seguranca
from sqlalchemy import delete

from app.extensions import db
from app.models import User

pytestmark = pytest.mark.banco

SENHA = "Senha-sintetica-tempo-2026"


def _csrf(resposta):
    return re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', resposta.get_data(as_text=True)
    ).group(1)


@pytest.fixture
def contas(app_com_banco):
    sufixo = uuid4().hex[:10]
    ativo, inativo = f"tempo-a-{sufixo}", f"tempo-i-{sufixo}"
    with app_com_banco.app_context():
        for nome, ligado in ((ativo, True), (inativo, False)):
            conta = User(username=nome, role="operador", is_active_user=ligado)
            conta.set_password(SENHA)
            db.session.add(conta)
        db.session.commit()
    yield ativo, inativo, f"tempo-x-{sufixo}"
    with app_com_banco.app_context():
        db.session.execute(delete(User).where(User.username.in_([ativo, inativo])))
        db.session.commit()


def _tentar(app, nome, senha, chamadas, monkeypatch):
    original = seguranca.check_password_hash

    def contar(*args, **kwargs):
        chamadas.append(1)
        return original(*args, **kwargs)

    cliente = app.test_client()
    cliente.environ_base["REMOTE_ADDR"] = "2001:db8::" + uuid4().hex[:4] + ":" + uuid4().hex[:4]
    token = _csrf(cliente.get("/login"))
    monkeypatch.setattr(seguranca, "check_password_hash", contar)
    return cliente.post(
        "/login", data={"username": nome, "password": senha, "csrf_token": token}
    )


@pytest.mark.parametrize(
    ("caso", "senha", "status"),
    [
        ("inexistente", SENHA, 401),
        ("inativo", SENHA, 401),
        ("ativo", "senha-errada-qualquer", 401),
        ("ativo", SENHA, 302),
    ],
)
def test_todo_caminho_do_login_paga_o_hash_uma_vez(
    app_com_banco, contas, monkeypatch, caso, senha, status
):
    ativo, inativo, inexistente = contas
    nome = {"inexistente": inexistente, "inativo": inativo, "ativo": ativo}[caso]
    chamadas: list[int] = []
    resposta = _tentar(app_com_banco, nome, senha, chamadas, monkeypatch)
    assert resposta.status_code == status
    assert len(chamadas) == 1
