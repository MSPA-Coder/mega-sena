from __future__ import annotations

import os
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import sqlalchemy as sa
from flask import Flask
from openpyxl import Workbook

from app import create_app

TEST_DATABASE_URL_ENV = "TEST_DATABASE_URL"


def get_test_database_url() -> str:
    """Retorna a URL do PostgreSQL descartável usado pela suíte de testes.

    A suíte não usa SQLite para simular persistência (veja AGENTS.md). É
    necessário um PostgreSQL real e descartável, apontado por
    `TEST_DATABASE_URL` (ou `DATABASE_URL` como alternativa, útil no Docker
    Compose de desenvolvimento). Veja docs/development.md.
    """
    url = os.environ.get(TEST_DATABASE_URL_ENV, "").strip() or os.environ.get(
        "DATABASE_URL", ""
    ).strip()
    if not url:
        raise RuntimeError(
            "TEST_DATABASE_URL (ou DATABASE_URL) não definida. A suíte de "
            "testes exige um PostgreSQL descartável; veja docs/development.md."
        )
    return url


_schema_ready_urls: set[str] = set()


def _ensure_schema_ready(database_url: str) -> None:
    """Aplica as migrações Alembic uma única vez por URL, por processo de teste.

    Só é chamada por testes que efetivamente usam `make_app()` (persistência,
    integração, HTTP). Testes puros em `tests/unit/` nunca chamam `make_app()`
    e, portanto, nunca precisam de um PostgreSQL disponível — conforme
    AGENTS.md ("testes unitários de cálculos, normalização, validações e
    regras de domínio não usam banco").
    """
    if database_url in _schema_ready_urls:
        return
    from app.schema import ensure_database_schema

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": database_url,
            "SECRET_KEY": "schema-setup",
        }
    )
    with app.app_context():
        ensure_database_schema(app)
    _schema_ready_urls.add(database_url)


def _reset_test_database(database_url: str) -> None:
    """Deixa o PostgreSQL descartável em um estado limpo antes de cada teste.

    O schema é criado uma única vez por URL (`_ensure_schema_ready`, via
    Alembic). O isolamento entre testes é feito por TRUNCATE das tabelas de
    aplicação, preservando `alembic_version`. Isso evita recriar o schema a
    cada teste e mantém o comportamento anterior (banco vazio a cada teste),
    agora sobre um banco real em vez de um SQLite efêmero em memória.
    """
    engine = sa.create_engine(database_url, poolclass=sa.pool.NullPool)
    try:
        with engine.connect() as connection:
            table_names = [
                name
                for name in sa.inspect(engine).get_table_names()
                if name != "alembic_version"
            ]
            if not table_names:
                return
            quoted = ", ".join(f'"{name}"' for name in table_names)
            with connection.begin():
                connection.execute(
                    sa.text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
                )
    finally:
        engine.dispose()


def make_app(database_url: str | None = None) -> Flask:
    """Cria a aplicação de teste pela mesma factory usada em produção.

    Garante o schema (uma vez por processo) e reseta o PostgreSQL descartável
    antes de construir a aplicação, garantindo que cada teste comece de um
    banco limpo.
    """
    url = database_url or get_test_database_url()
    _ensure_schema_ready(url)
    _reset_test_database(url)
    return create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": url,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SECRET_KEY": "test",
        }
    )


def csrf_form_data(client, token_path: str, data: dict | None = None) -> dict:
    text = client.get(token_path).get_data(as_text=True)
    marker = 'name="_csrf_token" value="'
    start = text.index(marker) + len(marker)
    end = text.index('"', start)
    payload = dict(data or {})
    payload["_csrf_token"] = text[start:end]
    return payload


def workbook_bytes(rows: list[list[object]], bad_dimension: bool = False) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "Concurso",
            "Data do Sorteio",
            "Bola1",
            "Bola2",
            "Bola3",
            "Bola4",
            "Bola5",
            "Bola6",
            "Ganhadores 6 acertos",
            "Ganhadores 5 acertos",
            "Ganhadores 4 acertos",
            "Rateio 6 acertos",
            "Rateio 5 acertos",
            "Rateio 4 acertos",
            "Acumulado 6 acertos",
        ]
    )
    for row in rows:
        sheet.append(row)

    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    if not bad_dimension:
        return stream

    patched = BytesIO()
    with ZipFile(stream, "r") as source, ZipFile(patched, "w", ZIP_DEFLATED) as target:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                content = content.replace(
                    b'<dimension ref="A1:O3"/>', b'<dimension ref="A1:O1"/>'
                )
            target.writestr(info, content)
    patched.seek(0)
    return patched
