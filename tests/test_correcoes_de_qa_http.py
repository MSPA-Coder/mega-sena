"""Regressões da rodada de QA de 21/10/2026, pela porta pública (HTTP).

Cada teste prende um defeito ou melhoria de uso que foi corrigido: o que a
pessoa vê ou recebe, não o texto do código.
"""

from __future__ import annotations

import re

import pytest

from app.accounts import service as contas
from app.bets import service as geracao
from app.bets.criteria import GENERATION_LIMITS
from app.extensions import db
from app.models import AuditEvent, GeneratedBet, User

pytestmark = pytest.mark.banco

SENHA = "Synthetic-password-20261021"
NOME = "qa_http_regressao"
LOTE_SENTINELA = 987_654_321


def _csrf(response):
    return re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    ).group(1)


@pytest.fixture(scope="module")
def logado(app_com_banco):
    """Um login para o módulo todo: o limitador de tentativas barra dezenas."""
    with app_com_banco.app_context():
        antigo = User.query.filter_by(username=NOME).first()
        if antigo is not None:
            AuditEvent.query.filter_by(actor_user_id=antigo.id).delete()
            db.session.delete(antigo)
        usuario = User(username=NOME, role="admin")
        usuario.set_password(SENHA)
        db.session.add(usuario)
        db.session.commit()
        user_id = usuario.id
    client = app_com_banco.test_client()
    client.post(
        "/login",
        data={"username": NOME, "password": SENHA, "csrf_token": _csrf(client.get("/login"))},
    )
    yield client
    with app_com_banco.app_context():
        db.session.rollback()
        GeneratedBet.query.filter_by(generation_id=LOTE_SENTINELA).delete()
        AuditEvent.query.filter_by(actor_user_id=user_id).delete()
        db.session.delete(db.session.get(User, user_id))
        db.session.commit()


# --- D1: fechamento de 10 a 20 dezenas grava sem exigir "quantidade" ---------


def test_fechamento_de_dez_dezenas_grava_as_210_apostas(app_com_banco, logado):
    token = _csrf(logado.get("/bets"))
    with app_com_banco.app_context():
        antes = GeneratedBet.query.count()
    resposta = logado.post(
        "/bets",
        data={
            "action": "save_closure",
            "closure_numbers": "01 05 10 15 20 25 30 35 40 45",
            "csrf_token": token,
        },
    )
    assert resposta.status_code == 302
    with app_com_banco.app_context():
        assert GeneratedBet.query.count() - antes == 210
        ultimo = GeneratedBet.query.order_by(GeneratedBet.id.desc()).first()
        GeneratedBet.query.filter_by(generation_id=ultimo.generation_id).delete()
        db.session.commit()


# --- D2: excluir aposta pede confirmação -------------------------------------


def test_exclusao_de_aposta_salva_declara_confirmacao_no_botao(app_com_banco, logado):
    with app_com_banco.app_context():
        db.session.add(
            GeneratedBet(
                generation_id=LOTE_SENTINELA,
                quantity=6,
                numbers_csv="1,2,3,4,5,6",
                score=0,
            )
        )
        db.session.commit()
    pagina = logado.get("/bets").get_data(as_text=True)
    assert 'data-sa-confirmar="Excluir esta aposta salva?"' in pagina


# --- D3: sequência 0 não é aceita nem sugerida --------------------------------


def test_sequencia_consecutiva_zero_e_recusada_na_geracao(logado):
    resposta = logado.post(
        "/bets",
        data={
            "action": "generate",
            "quantity": "6",
            "amount": "1",
            "consecutive_count": "0",
            "csrf_token": _csrf(logado.get("/bets")),
        },
        headers={"HX-Request": "true"},
    )
    assert resposta.status_code == 400
    assert "flash-error" in resposta.get_data(as_text=True)


def test_limite_da_sequencia_consecutiva_comeca_em_um():
    assert GENERATION_LIMITS["consecutive_count"] == (1, 6)


# --- D4: gerações pesadas não esgotam o servidor ------------------------------


def test_geracao_recusa_quando_as_vagas_estao_ocupadas():
    vagas = [
        geracao._GENERATION_SLOTS.acquire(blocking=False)
        for _ in range(geracao.MAX_CONCURRENT_GENERATIONS)
    ]
    try:
        with pytest.raises(RuntimeError, match="Aguarde"):
            geracao.generate_bets(1, 6, {})
    finally:
        for ocupou in vagas:
            if ocupou:
                geracao._GENERATION_SLOTS.release()


# --- D5: ids além de int32 respondem 404, não 500 --------------------------


@pytest.mark.parametrize(
    "rota",
    [
        "/bets/saved/99999999999/delete",
        "/usuarios/99999999999/senha",
        "/usuarios/99999999999/ativo",
        "/usuarios/99999999999/papel",
    ],
)
def test_id_fora_do_intervalo_do_banco_responde_404(logado, rota):
    token = _csrf(logado.get("/bets"))
    assert logado.post(rota, data={"csrf_token": token}).status_code == 404


# --- D6: nome de usuário longo é recusado com mensagem -----------------------


def test_nome_de_usuario_acima_de_80_caracteres_e_recusado(app_com_banco):
    with app_com_banco.app_context(), pytest.raises(contas.UserManagementError, match="80"):
        contas.provision_cli_user("u" * 81, SENHA)


# --- U1/U2/U3/U8: formulário de geração --------------------------------------


def test_pagina_de_geracao_expoe_campo_de_dezenas_e_pontos_de_navegacao(logado):
    pagina = logado.get("/bets").get_data(as_text=True)
    assert 'id="generation-quantity"' in pagina
    assert 'class="skip-link"' in pagina


def test_previa_com_filtro_contraditorio_mostra_erro_em_vez_de_corrigir(logado):
    resposta = logado.get(
        "/bets/preview?quantity=6&amount=1&even_min=5&even_max=2",
        headers={"HX-Request": "true"},
    )
    assert resposta.status_code == 200
    assert "flash-error" in resposta.get_data(as_text=True)


# --- U7: filtros e busca na tela de concursos --------------------------------


def test_concursos_aceitam_busca_por_numero_e_filtros_de_pares_e_sequencia(logado):
    resposta = logado.get("/contests?contest=1&even_count=3&consecutive_count=2")
    assert resposta.status_code == 200
    html = resposta.get_data(as_text=True)
    assert 'id="contest-search"' in html
    assert 'name="even_count"' in html
    assert 'name="consecutive_count"' in html


# --- U8: títulos únicos por página -------------------------------------------


@pytest.mark.parametrize(
    ("rota", "titulo"),
    [
        ("/dashboard", "Dashboard"),
        ("/contests", "Concursos"),
        ("/settings", "Configurações"),
        ("/usuarios", "Usuários"),
        ("/bets", "Gerar apostas"),
    ],
)
def test_cada_pagina_tem_titulo_proprio_e_h1(logado, rota, titulo):
    html = logado.get(rota).get_data(as_text=True)
    assert f"<title>{titulo} · Mega Sena AI</title>" in html
    assert re.search(rf"<h1[^>]*>\s*{titulo}\s*</h1>", html)


def test_graficos_do_dashboard_tem_alternativa_em_texto(logado):
    html = logado.get("/dashboard").get_data(as_text=True)
    assert re.search(r'id="sum-histogram"[^>]*role="img"[^>]*aria-label="', html)
    assert re.search(r'id="freq-chart"[^>]*role="img"[^>]*aria-label="', html)
