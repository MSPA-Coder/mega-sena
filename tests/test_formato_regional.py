"""Formato regional (Brasil/EUA) por usuário: só apresentação.

Risco que protege: o usuário escolher EUA e ver data ou número em formato
trocado pela metade, ou a escolha de um usuário vazar para a requisição
seguinte. O que é gravado, importado e calculado não passa por esta camada e
não deve mudar.

A suíte não toca o banco (ver `conftest.py`): o carregamento de usuário é
trocado por um objeto em memória e o `commit` do serviço é substituído.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pytest

from app.accounts import service
from app.core import regional
from app.core.formatting import format_brl_without_cents, format_int, format_percent
from app.core.regional import REGIONAL_FORMAT_BR, REGIONAL_FORMAT_US, normalize_regional_format
from app.extensions import login_manager
from app.models import ROLE_OPERADOR, User

RAIZ = Path(__file__).resolve().parent.parent


def _usuario(formato: str = "br") -> User:
    return User(
        id=1, username="fulano", role=ROLE_OPERADOR, is_active_user=True,
        must_change_password=False, regional_format=formato,
    )


def _logar(client, user: User) -> None:
    login_manager._user_callback = lambda _id: user
    with client.session_transaction() as sessao:
        sessao["_user_id"] = str(user.id)
        sessao["_fresh"] = True


@pytest.fixture
def eua():
    token = regional.ativar(REGIONAL_FORMAT_US)
    yield
    regional.desativar(token)


def test_sem_requisicao_vale_o_formato_do_brasil():
    assert regional.formato_ativo() == REGIONAL_FORMAT_BR
    assert regional.formatar_data(date(2026, 12, 31)) == "31/12/2026"
    assert regional.formatar_data_hora(datetime(2026, 12, 31, 8, 5, 9), segundos=True) == "31/12/2026 08:05:09"


def test_formato_desconhecido_cai_no_brasil():
    assert normalize_regional_format("xx") == REGIONAL_FORMAT_BR
    assert normalize_regional_format(None) == REGIONAL_FORMAT_BR


def test_numeros_no_brasil_continuam_iguais():
    assert format_int(1234567) == "1.234.567"
    assert format_percent(12.5) == "12,5"
    assert format_brl_without_cents(123456) == "R$ 1.235"


def test_numeros_nos_eua_trocam_so_os_separadores(eua):
    assert format_int(1234567) == "1,234,567"
    assert format_percent(12.5) == "12.5"
    assert format_brl_without_cents(123456) == "R$ 1,235"
    assert regional.formatar_data(date(2026, 12, 31)) == "12/31/2026"


def test_data_ausente_nao_vira_texto(app):
    assert app.jinja_env.filters["udate"](None) == ""


def test_a_tela_usa_o_formato_do_usuario_e_nao_vaza(app, client, monkeypatch):
    monkeypatch.setattr(service.db.session, "commit", lambda: None)
    _logar(client, _usuario("us"))
    assert 'data-regional="us"' in client.get("/preferencias").get_data(as_text=True)
    assert regional.formato_ativo() == REGIONAL_FORMAT_BR

    _logar(client, _usuario("br"))
    assert 'data-regional="br"' in client.get("/preferencias").get_data(as_text=True)


def test_preferencias_mostra_as_duas_opcoes_e_a_escolhida(app, client):
    _logar(client, _usuario("us"))
    html = client.get("/preferencias").get_data(as_text=True)
    assert 'name="regional_format"' in html
    assert re.search(r'value="us"[^>]*checked', html)
    assert not re.search(r'value="br"[^>]*checked', html)


def test_preferencias_grava_para_o_proprio_usuario_e_recusa_valor_estranho(app, client, monkeypatch):
    app.config["WTF_CSRF_ENABLED"] = False
    monkeypatch.setattr(service.db.session, "commit", lambda: None)
    usuario = _usuario("br")
    _logar(client, usuario)

    assert client.post("/preferencias", data={"regional_format": "us"}).status_code == 302
    assert usuario.regional_format == REGIONAL_FORMAT_US

    client.post("/preferencias", data={"regional_format": "../x"})
    assert usuario.regional_format == REGIONAL_FORMAT_BR


def test_preferencias_exige_login(client):
    resposta = client.get("/preferencias", follow_redirects=False)
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_nenhum_template_formata_data_fora_do_filtro_regional():
    """Data legível por pessoa passa por `udate`, nunca por texto cru nem `strftime` fixo."""
    fixos = []
    for caminho in (RAIZ / "app" / "templates").rglob("*.html"):
        texto = caminho.read_text(encoding="utf-8")
        if re.search(r"draw_date(?!\|udate)\b", texto) or "strftime(" in texto:
            fixos.append(caminho.relative_to(RAIZ).as_posix())
    assert not fixos, fixos


def test_o_javascript_regional_ignora_o_auxiliar_do_calendario():
    """O campo auxiliar do calendario nunca vira campo regional.

    Risco que protege: o auxiliar e um `<input type="date">` dentro do wrapper.
    Sem a guarda, conteudo inserido depois do carregamento (troca de HTMX, campo
    criado por JS) faz o observador tratar o auxiliar como campo novo e criar
    wrapper dentro de wrapper sem fim, travando a aba.
    """
    texto = (RAIZ / "app/static/regional.js").read_text(encoding="utf-8")
    assert "classList.contains('regional-picker-proxy')" in texto
    assert ":not(.regional-picker-proxy)" in texto


def test_numero_simples_segue_o_formato(app, eua):
    assert app.jinja_env.filters["unumber"](80.0) == "80.0"
    assert app.jinja_env.filters["unumber"](12.5) == "12.5"


def test_numero_simples_no_brasil_usa_virgula(app):
    assert app.jinja_env.filters["unumber"](80.0) == "80,0"


def test_nenhum_template_formata_decimal_com_ponto_fixo():
    """Decimal na tela passa por `unumber`; `%.2f` e `_pct` crus mostrariam ponto a quem usa Brasil."""
    cru = []
    for caminho in (RAIZ / "app" / "templates").rglob("*.html"):
        texto = caminho.read_text(encoding="utf-8")
        if re.search(r'\{\{\s*"%\.\d+f"\|format\([^)]*\)\s*\}\}', texto) or re.search(r"_pct\s*\}\}", texto):
            cru.append(caminho.relative_to(RAIZ).as_posix())
    assert not cru, cru
