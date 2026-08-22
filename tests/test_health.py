"""A sonda de saude responde sem sessao e depende mesmo do banco.

A sonda dedicada nao pode usar a raiz do site, que redireciona para `/login`
sem sessao e poderia produzir um falso positivo sem consultar o banco.

A suite nao tem banco (ver `conftest.py`), o que aqui e vantagem e nao
limitacao: e exatamente o cenario "banco inalcancavel" que a rota precisa
detectar.
"""

from __future__ import annotations


def test_health_responde_sem_sessao(client):
    # Nao 302 para /login: o Docker consulta de dentro da rede do Compose,
    # sem cookie nenhum.
    assert client.get("/health").status_code != 302


def test_health_reporta_erro_quando_o_banco_esta_inalcancavel(client):
    resposta = client.get("/health")
    assert resposta.status_code == 503
    assert resposta.get_json() == {"servico": "mega-sena", "status": "erro"}


def test_health_nao_vaza_detalhe_de_infraestrutura(client):
    # A resposta de erro nao pode virar reconhecimento gratuito: nada de
    # host, porta, nome de banco ou traceback.
    corpo = client.get("/health").get_data(as_text=True).lower()
    for termo in ("postgres", "psycopg", "localhost", "5432", "traceback", "password"):
        assert termo not in corpo
