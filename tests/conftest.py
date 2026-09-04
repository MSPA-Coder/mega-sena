"""Fixtures da suite minima.

A suite nao toca o banco. Isso e desenho, nao limitacao: as quatro coisas que
ela protege -- cabecalhos, negacao por padrao, CSRF e integridade do grafo de
migracoes -- sao decididas antes de qualquer consulta. Isso mantem a execucao
rapida e sem infraestrutura de banco para teste.

O bootstrap do schema em PostgreSQL vazio continua sendo verificacao manual
obrigatoria para mudanca de schema, como a base registra.
"""

from __future__ import annotations

import psycopg
import pytest

from app import create_app


def _banco_inalcancavel() -> object:
    """`creator` do engine: recusa a conexao na hora, sem abrir socket.

    `/health` (ver `test_health.py`) e as rotas por tras da troca de senha
    (ver `test_troca_de_senha.py`) tocam o banco de proposito -- e exatamente
    isso que essas suites medem. Sem um creator, o SQLAlchemy tentaria abrir
    TCP de verdade contra o Postgres inexistente de `SQLALCHEMY_DATABASE_URI`
    (a URI so serve para o dialeto ser reconhecido) e dependeria do sistema
    operacional recusar a conexao.

    No Linux essa recusa e imediata, mas no Windows (psycopg 3.2.13 com
    Python 3.14, pelo menos) `psycopg.waiting.wait_conn` prende a suite para
    sempre: o socket sinaliza a falha so em `exceptfds`, e o laco de
    `selectors.py` nunca chega a olhar ali, so em `readfds`/`writefds`.
    `connect_timeout` na URI nao ajuda -- o prazo e conferido dentro do mesmo
    laco que ja esta preso, entao nunca e avaliado.

    Levantar `psycopg.OperationalError` aqui, antes de qualquer socket,
    reproduz a MESMA excecao que o SQLAlchemy converteria a partir de uma
    recusa de conexao real, so que instantanea e igual em qualquer sistema
    operacional.
    """
    raise psycopg.OperationalError("suite de testes sem banco: conexao recusada")


@pytest.fixture
def app():
    # `create_app` valida o formato da URL mas nao conecta: nenhuma das rotas
    # exercitadas aqui chega a consultar o banco de verdade -- o `creator`
    # acima e quem garante isso ao recusar a conexao antes do socket.
    application = create_app(
        {
            "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://test:test@localhost:5432/test",
            "SECRET_KEY": "chave-de-teste-nao-usada-em-execucao-real",
            "TESTING": True,
            "SQLALCHEMY_ENGINE_OPTIONS": {"creator": _banco_inalcancavel},
        }
    )
    return application


@pytest.fixture
def client(app):
    return app.test_client()
