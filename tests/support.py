from __future__ import annotations

import os
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import sqlalchemy as sa
from flask import Flask
from openpyxl import Workbook

from app import create_app

TEST_DATABASE_URL_ENV = "TEST_DATABASE_URL"


def _database_identity(url: str) -> tuple[str, int, str]:
    parsed = sa.make_url(url)
    if parsed.get_backend_name() != "postgresql":
        raise RuntimeError("TEST_DATABASE_URL deve apontar para PostgreSQL.")
    database = (parsed.database or "").strip()
    if not database:
        raise RuntimeError("TEST_DATABASE_URL deve identificar um banco.")
    return ((parsed.host or "").casefold(), parsed.port or 5432, database.casefold())


def get_test_database_url() -> str:
    """Retorna a URL do PostgreSQL descartável usado pela suíte de testes.

    A suíte não usa SQLite para simular persistência (veja AGENTS.md). É
    necessário um PostgreSQL real e descartável, apontado exclusivamente por
    `TEST_DATABASE_URL`. Não use `DATABASE_URL`: ela identifica o banco da
    aplicação e a limpeza entre testes poderia apagar seus dados. Veja
    docs/development.md.
    """
    url = os.environ.get(TEST_DATABASE_URL_ENV, "").strip()
    if not url:
        raise RuntimeError(
            "TEST_DATABASE_URL não definida. A suíte de testes exige um "
            "PostgreSQL descartável; veja docs/development.md."
        )
    test_identity = _database_identity(url)
    if test_identity[2] == "postgres" or not test_identity[2].endswith("_test"):
        raise RuntimeError(
            "TEST_DATABASE_URL deve usar um banco descartável cujo nome termine "
            "em '_test'; bancos operacionais ou de manutenção são recusados."
        )
    application_url = os.environ.get("DATABASE_URL", "").strip()
    if application_url:
        try:
            application_identity = _database_identity(application_url)
        except (RuntimeError, sa.exc.ArgumentError):
            application_identity = None
        if application_identity == test_identity:
            raise RuntimeError(
                "TEST_DATABASE_URL aponta para o mesmo banco de DATABASE_URL; "
                "a suíte se recusa a limpar o banco da aplicação."
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
            from app.extensions import db

            existing_tables = set(sa.inspect(engine).get_table_names())
            table_names = [
                name for name in db.metadata.tables if name in existing_tables
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
