"""Minhas apostas, Resultados e Importar resultados, pela porta pública (HTTP).

Antes, a tela Gerar apostas guardava o histórico das apostas gravadas (as 12
últimas gerações, sem paginação) e a tela Concursos guardava a importação. Cada
tela agora faz uma coisa: o que se confere está em Minhas apostas, o que se
consulta em Resultados e o que se traz de fora em Importar resultados.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from app.extensions import db
from app.models import AuditEvent, GeneratedBet, User

pytestmark = pytest.mark.banco

SENHA = "Synthetic-password-20261030"
NOME = "qa_minhas_apostas"
# Concurso e lotes que nenhum outro teste usa: a lista é filtrada por ele, então
# gerações deixadas por outros testes no banco não entram na conta.
CONCURSO = 987_000_001
PRIMEIRO_LOTE = 970_000_001
LOTES = 12


def _csrf(response):
    return re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    ).group(1)


def _ativos(html: str) -> list[str]:
    """Rótulos dos links do menu com a classe `active` (grupos não entram)."""
    return re.findall(r'<a class="active" href="[^"]*"[^>]*>([^<]+)</a>', html)


def _grupos_ativos(html: str) -> list[str]:
    return re.findall(r'<div class="nav-group active"[^>]*>\s*<button[^>]*>([^<]+)<', html)


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
        AuditEvent.query.filter_by(actor_user_id=user_id).delete()
        db.session.delete(db.session.get(User, user_id))
        db.session.commit()


@pytest.fixture
def lotes(app_com_banco):
    """Doze gerações do mesmo concurso, a mais antiga com o menor id."""
    inicio = datetime(2098, 1, 1, tzinfo=UTC)
    with app_com_banco.app_context():
        for indice in range(LOTES):
            db.session.add(
                GeneratedBet(
                    generation_id=PRIMEIRO_LOTE + indice,
                    contest=CONCURSO,
                    quantity=6,
                    numbers_csv="1,2,3,4,5,6",
                    score=0,
                    created_at=inicio + timedelta(minutes=indice),
                )
            )
        db.session.commit()
    yield
    with app_com_banco.app_context():
        db.session.rollback()
        GeneratedBet.query.filter_by(contest=CONCURSO).delete()
        db.session.commit()


def _geracoes_na_pagina(html: str) -> list[int]:
    return [int(n) for n in re.findall(r"Geração #(\d+)</strong>", html)]


def test_gerar_apostas_nao_mostra_mais_o_historico(logado, lotes):
    html = logado.get("/bets").get_data(as_text=True)

    assert "generation-group" not in html
    assert "Últimas apostas geradas" not in html
    assert _ativos(html) == ["Gerar apostas"]
    assert _grupos_ativos(html) == ["Apostas"]


def test_minhas_apostas_pagina_de_dez_em_dez_da_mais_recente_para_a_mais_antiga(logado, lotes):
    primeira = logado.get(f"/bets/minhas?contest={CONCURSO}").get_data(as_text=True)
    segunda = logado.get(f"/bets/minhas?contest={CONCURSO}&page=2").get_data(as_text=True)

    ultimo = PRIMEIRO_LOTE + LOTES - 1
    assert _geracoes_na_pagina(primeira) == list(range(ultimo, ultimo - 10, -1))
    assert _geracoes_na_pagina(segunda) == [PRIMEIRO_LOTE + 1, PRIMEIRO_LOTE]
    assert "Página 1/2" in primeira and "Página 2/2" in segunda
    assert f"{LOTES} gerações do concurso {CONCURSO}" in primeira
    assert _ativos(primeira) == ["Minhas apostas"]
    assert _grupos_ativos(primeira) == ["Apostas"]


def test_pagina_fora_do_intervalo_vira_a_ultima(logado, lotes):
    html = logado.get(f"/bets/minhas?contest={CONCURSO}&page=99").get_data(as_text=True)

    assert "Página 2/2" in html
    assert _geracoes_na_pagina(html) == [PRIMEIRO_LOTE + 1, PRIMEIRO_LOTE]


def test_filtro_por_concurso_sem_apostas_explica_em_vez_de_mostrar_lista_vazia(logado, lotes):
    html = logado.get("/bets/minhas?contest=987000099").get_data(as_text=True)

    assert "Nenhuma aposta gravada para o concurso 987000099." in html
    assert "generation-group" not in html


@pytest.mark.parametrize("consulta", ["page=abc", "contest=xyz", "page=-3&contest=", "page=0"])
def test_parametros_invalidos_nao_derrubam_a_tela(logado, consulta):
    assert logado.get(f"/bets/minhas?{consulta}").status_code == 200


def test_excluir_volta_para_a_mesma_pagina_e_filtro(app_com_banco, logado, lotes):
    with app_com_banco.app_context():
        aposta = GeneratedBet.query.filter_by(generation_id=PRIMEIRO_LOTE).one().id
    token = _csrf(logado.get("/bets"))

    resposta = logado.post(
        f"/bets/saved/{aposta}/delete",
        data={"csrf_token": token, "page": "2", "contest": str(CONCURSO)},
    )

    assert resposta.status_code == 302
    destino = urlsplit(resposta.headers["Location"])
    assert destino.path == "/bets/minhas"
    assert parse_qs(destino.query) == {"page": ["2"], "contest": [str(CONCURSO)]}
    with app_com_banco.app_context():
        assert GeneratedBet.query.filter_by(generation_id=PRIMEIRO_LOTE).count() == 0


def test_excluir_ignora_destino_que_nao_seja_numero(logado, lotes, app_com_banco):
    """Só números entram no redirecionamento: o formulário não escolhe o destino."""
    with app_com_banco.app_context():
        aposta = GeneratedBet.query.filter_by(generation_id=PRIMEIRO_LOTE).one().id
    token = _csrf(logado.get("/bets"))

    resposta = logado.post(
        f"/bets/saved/{aposta}/delete",
        data={"csrf_token": token, "page": "https://outro.site/", "contest": "../x"},
    )

    assert urlsplit(resposta.headers["Location"]).path == "/bets/minhas"
    assert urlsplit(resposta.headers["Location"]).netloc == ""


def test_resultados_so_consulta_e_importar_resultados_so_importa(logado):
    resultados = logado.get("/contests").get_data(as_text=True)
    importar = logado.get("/contests/importar").get_data(as_text=True)

    assert 'name="file"' not in resultados
    assert 'id="contest-search"' in resultados
    assert _ativos(resultados) == ["Resultados"]
    assert _grupos_ativos(resultados) == ["Concursos"]

    assert 'name="file"' in importar
    assert 'id="contest-search"' not in importar
    assert _ativos(importar) == ["Importar resultados"]


def test_importacao_recusada_sem_htmx_volta_para_a_tela_de_importar(logado):
    token = _csrf(logado.get("/contests/importar"))

    resposta = logado.post("/contests/import", data={"csrf_token": token})

    assert resposta.status_code == 302
    assert urlsplit(resposta.headers["Location"]).path == "/contests/importar"


def test_importacao_recusada_com_htmx_devolve_so_o_aviso(logado):
    token = _csrf(logado.get("/contests/importar"))

    resposta = logado.post(
        "/contests/import", data={"csrf_token": token}, headers={"HX-Request": "true"}
    )

    html = resposta.get_data(as_text=True)
    assert resposta.status_code == 200
    assert 'id="import-feedback"' in html
    assert "Selecione uma planilha" in html
    assert "contests-results" not in html
