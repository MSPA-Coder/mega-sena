"""Fixtures da suite minima.

A suite nao toca o banco. Isso e desenho, nao limitacao: as quatro coisas que
ela protege -- cabecalhos, negacao por padrao, CSRF e integridade do grafo de
migracoes -- sao decididas antes de qualquer consulta, e mante-la sem banco e o
que faz caber no orcamento de 30 segundos sem infraestrutura de teste.

O bootstrap do schema em PostgreSQL vazio continua sendo verificacao manual
obrigatoria para mudanca de schema, como a base registra.
"""

from __future__ import annotations

import pytest

from app import create_app


@pytest.fixture
def app():
    # `create_app` valida o formato da URL mas nao conecta: nenhuma das rotas
    # exercitadas aqui chega a consultar o banco.
    application = create_app(
        {
            "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://test:test@localhost:5432/test",
            "SECRET_KEY": "chave-de-teste-nao-usada-em-execucao-real",
            "TESTING": True,
        }
    )
    return application


@pytest.fixture
def client(app):
    return app.test_client()
