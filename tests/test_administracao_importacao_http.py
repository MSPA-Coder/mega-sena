"""Administração e importação autenticadas com CSRF e PostgreSQL reais."""

import re
from io import BytesIO
from uuid import uuid4

import pytest
from openpyxl import Workbook
from sqlalchemy import delete

from app.extensions import db
from app.models import AuditEvent, Draw, ImportBatch, User

pytestmark = pytest.mark.banco


def csrf(response):
    return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)).group(1)


@pytest.fixture
def acesso(app_com_banco):
    app = app_com_banco
    nomes = ["qa-http-" + uuid4().hex[:12] for _ in range(2)]
    with app.app_context():
        usuarios = [User(username=nome, role=papel, is_active_user=True, must_change_password=False)
                    for nome, papel in zip(nomes, ("admin", "operador"), strict=True)]
        for usuario in usuarios:
            usuario.set_password("Senha-sintetica-qa-2026")
        db.session.add_all(usuarios)
        db.session.commit()
        ids = [u.id for u in usuarios]
    clientes = []
    for nome in nomes:
        cliente = app.test_client()
        cliente.environ_base["REMOTE_ADDR"] = "2001:db8::" + uuid4().hex[:4] + ":" + uuid4().hex[:4]
        token = csrf(cliente.get("/login"))
        assert cliente.post("/login", data={"username": nome, "password": "Senha-sintetica-qa-2026",
                                           "csrf_token": token}).status_code == 302
        clientes.append((cliente, token))
    yield app, ids, clientes
    with app.app_context():
        db.session.rollback()
        db.session.execute(delete(Draw).where(Draw.contest == 98765))
        db.session.execute(delete(ImportBatch).where(ImportBatch.actor_user_id.in_(ids)))
        db.session.execute(delete(AuditEvent).where(AuditEvent.actor_user_id.in_(ids)))
        db.session.execute(delete(User).where(User.id.in_(ids)))
        db.session.commit()


def planilha(numeros=(1, 2, 3, 4, 5, 6)):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Concurso", "Data Sorteio", *[f"Bola {i}" for i in range(1, 7)]])
    sheet.append([98765, "01/08/2026", *numeros])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    stream.seek(0)
    return stream


def test_importacao_http_idempotente_normaliza_nome_e_mantem_proveniencia(acesso):
    app, ids, clientes = acesso
    cliente, token = clientes[0]
    for _ in range(2):
        response = cliente.post("/contests/import", data={"csrf_token": token,
                               "file": (planilha(), "../../temporario/resultados.xlsx")})
        assert response.status_code == 302
    with app.app_context():
        assert Draw.query.filter_by(contest=98765).count() == 1
        lotes = ImportBatch.query.filter_by(actor_user_id=ids[0]).order_by(ImportBatch.id).all()
        assert len(lotes) == 2
        assert lotes[0].source_name == "resultados.xlsx"
        assert lotes[0].imported_count == 1 and lotes[1].ignored_count == 1
        assert lotes[0].content_sha256


@pytest.mark.parametrize("arquivo,nome", [(b"nao e xlsx", "quebrado.xlsx"), (b"x", "suspeito.exe")])
def test_importacao_invalida_nao_cria_concurso(acesso, arquivo, nome):
    app, _, clientes = acesso
    cliente, token = clientes[0]
    response = cliente.post("/contests/import", data={"csrf_token": token, "file": (BytesIO(arquivo), nome)})
    assert response.status_code == 302
    with app.app_context():
        assert Draw.query.filter_by(contest=98765).first() is None


def test_autodesativacao_e_papel_invalido_preservam_acesso_administrativo(acesso):
    app, ids, clientes = acesso
    cliente, token = clientes[0]
    assert cliente.post(f"/usuarios/{ids[0]}/ativo", data={"csrf_token": token, "active": "0"}).status_code == 302
    assert cliente.post(f"/usuarios/{ids[0]}/papel", data={"csrf_token": token, "role": "root"}).status_code == 302
    with app.app_context():
        usuario = db.session.get(User, ids[0])
        assert usuario.is_active_user and usuario.role == "admin"
        assert AuditEvent.query.filter_by(actor_user_id=ids[0], action="users.set_role", success=False).count() == 1


def test_admin_desativa_reativa_operador_e_operador_nao_altera_contas(acesso):
    app, ids, clientes = acesso
    admin, token = clientes[0]
    operador, token_operador = clientes[1]
    assert operador.post(f"/usuarios/{ids[0]}/ativo", data={"csrf_token": token_operador, "active": "0"}).status_code == 403
    for ativo in ("0", "1"):
        assert admin.post(f"/usuarios/{ids[1]}/ativo", data={"csrf_token": token, "active": ativo}).status_code == 302
        with app.app_context():
            assert db.session.get(User, ids[1]).is_active_user == (ativo == "1")
    with app.app_context():
        assert db.session.get(User, ids[0]).is_active_user
