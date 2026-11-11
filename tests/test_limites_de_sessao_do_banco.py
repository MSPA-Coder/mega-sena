"""Toda sessão da aplicação com o banco leva limites de comando, trava e ociosidade."""

import pytest
from sqlalchemy import text

from app import _opcoes_de_sessao_do_banco
from app.extensions import db

LIMITES = ("DB_STATEMENT_TIMEOUT_MS", "DB_LOCK_TIMEOUT_MS", "DB_IDLE_IN_TRANSACTION_TIMEOUT_MS")


@pytest.fixture(autouse=True)
def _sem_variaveis(monkeypatch):
    for nome in LIMITES:
        monkeypatch.delenv(nome, raising=False)


def test_padroes_sao_55s_10s_e_5min() -> None:
    assert _opcoes_de_sessao_do_banco() == (
        "-c statement_timeout=55000 -c lock_timeout=10000"
        " -c idle_in_transaction_session_timeout=300000"
    )


def test_zero_desliga_o_limite_de_comando_como_faz_o_migrate(monkeypatch) -> None:
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "0")
    assert "-c statement_timeout=0 " in _opcoes_de_sessao_do_banco()


@pytest.mark.parametrize("valor", ["abc", "-1"])
def test_valor_invalido_recusa_subir(monkeypatch, valor) -> None:
    monkeypatch.setenv("DB_LOCK_TIMEOUT_MS", valor)
    with pytest.raises(RuntimeError, match="DB_LOCK_TIMEOUT_MS"):
        _opcoes_de_sessao_do_banco()


@pytest.mark.banco
def test_o_servidor_aplica_os_limites_na_sessao_da_aplicacao(app_com_banco) -> None:
    with app_com_banco.app_context():
        valores = {
            parametro: db.session.execute(text(f"SHOW {parametro}")).scalar_one()
            for parametro in (
                "statement_timeout",
                "lock_timeout",
                "idle_in_transaction_session_timeout",
            )
        }
        db.session.rollback()
    assert valores == {
        "statement_timeout": "55s",
        "lock_timeout": "10s",
        "idle_in_transaction_session_timeout": "5min",
    }
