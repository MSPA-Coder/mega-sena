"""Fixtures da suite.

A suite tem DUAS CAMADAS, e a distincao importa ao escrever teste novo.

A CAMADA SEM BANCO e a maioria dos arquivos, e continua sendo desenho e nao
limitacao: cabecalhos, negacao por padrao, CSRF e integridade do grafo de
migracoes sao decididos antes de qualquer consulta, o que mantem a execucao
rapida e sem infraestrutura. As fixtures `app` e `client` servem a ela, com o
`creator` abaixo recusando a conexao antes de qualquer socket.

A CAMADA COM BANCO e o que a fase F1 do LEVANTAMENTO_2026-09.md acrescentou:
os testes marcados com `@pytest.mark.banco`, servidos por `app_com_banco` e
`sessao`. Ela existe porque o AGENTS.md declara que "as CHECK constraints de
`Draw` protegem valores derivados das dezenas" e pede para NAO duplicar essa
garantia com reparo silencioso em Python -- e uma garantia que vive so no
PostgreSQL nao pode ser verificada por uma suite que recusa a conexao.

O banco dessa camada e o servico `postgres-teste` do Compose: efemero, em
tmpfs, e deliberadamente NAO e o `postgres` com dados reais.

CONSEQUENCIA PRATICA: o bootstrap do schema em PostgreSQL vazio deixou de ser
verificacao manual. Uma migracao que falha ao executar agora reprova na CI, e
nao mais no `deploy.sh` -- que reverte codigo e imagem, mas nao reverte
migracao.

No venv, sem banco, o laco rapido e `pytest -q -m "not banco"`.
"""

from __future__ import annotations

import os
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Camada com banco (`@pytest.mark.banco`)
# ---------------------------------------------------------------------------


def _url_do_banco_de_teste() -> str:
    """Monta a URL a partir das variaveis `TESTE_POSTGRES_*` do Compose.

    O prefixo `TESTE_` nao e enfeite: a suite tem testes que medem o que a
    aplicacao faz quando uma variavel NAO existe, apagando-a do ambiente.
    Declarar `POSTGRES_HOST` e companhia no servico `quality` faria o app
    encontrar por arquivo o que o teste acabou de apagar. O motivo tambem esta
    escrito no `compose.yaml`, ao lado das variaveis.
    """
    from urllib.parse import quote

    faltando = [
        nome
        for nome in ("TESTE_POSTGRES_HOST", "TESTE_POSTGRES_DB", "TESTE_POSTGRES_USER")
        if not os.environ.get(nome)
    ]
    if faltando:
        pytest.skip(
            "camada com banco: rode pelo servico `quality` do Compose "
            f"(faltam {', '.join(faltando)})"
        )

    # O caminho e CONSTANTE, e nao uma variavel de ambiente, de proposito.
    # `/run/secrets/<nome>` e onde o Compose monta todo segredo de arquivo, e
    # ler o caminho do ambiente para depois abri-lo e exatamente o padrao que o
    # CodeQL sinaliza como "uncontrolled data used in path expression" -- com
    # razao, ainda que aqui a origem fosse o proprio compose.yaml. Sem o
    # intermediario nao existe sink, e o codigo fica mais curto.
    senha = Path("/run/secrets/postgres_password").read_text(encoding="utf-8").strip()
    return (
        "postgresql+psycopg://"
        f"{quote(os.environ['TESTE_POSTGRES_USER'])}:{quote(senha)}"
        f"@{os.environ['TESTE_POSTGRES_HOST']}:{os.environ.get('TESTE_POSTGRES_PORT', '5432')}"
        f"/{os.environ['TESTE_POSTGRES_DB']}"
    )


@pytest.fixture(scope="session")
def app_com_banco():
    """App real, ligado ao `postgres-teste`, com as migracoes aplicadas.

    O `upgrade()` aqui nao e cerimonia: e ele que faz cada execucao da suite
    aplicar TODAS as revisoes Alembic a um banco vazio. Uma revisao com SQL
    invalido, coluna `NOT NULL` acrescentada a tabela com linhas ou dependencia
    de extensao ausente derruba esta fixture, e a CI reprova.

    O `AGENTS.md` diz que `flask db upgrade` e etapa controlada e que
    `create_app()` nao aplica migracoes -- isso continua valendo. Aqui a
    migracao e chamada explicitamente pela fixture, que e o equivalente de
    teste do `docker-entrypoint.sh`, e nao pela fabrica.
    """
    from flask_migrate import upgrade

    aplicacao = create_app(
        {
            "SQLALCHEMY_DATABASE_URI": _url_do_banco_de_teste(),
            "SECRET_KEY": "chave-de-teste-nao-usada-em-execucao-real",
            "TESTING": True,
        }
    )
    with aplicacao.app_context():
        upgrade()
    return aplicacao


@pytest.fixture
def sessao(app_com_banco):
    """Sessao dentro de uma transacao que sempre e desfeita.

    Os testes desta camada usam `flush()` e nunca `commit()`: o `flush` envia o
    INSERT e faz a `CheckConstraint` disparar, que e o que se quer medir, sem
    deixar linha atras.
    """
    from app.models import db

    with app_com_banco.app_context():
        try:
            yield db.session
        finally:
            db.session.rollback()
            db.session.remove()
