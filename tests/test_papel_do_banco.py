"""A aplicação recusa atender como superusuário do PostgreSQL.

A suíte conecta com o papel administrativo, que é superusuário -- o mesmo
atributo que a produção tinha no papel da aplicação até 09/2026. Por isso a
recusa pode ser provada contra o servidor de verdade, e não só contra um dublê.
"""

from __future__ import annotations

import pytest
from sqlalchemy import event

from app.papel_do_banco import (
    VARIAVEL,
    PapelPrivilegiadoError,
    conferir_conexao,
)


class _CursorFalso:
    def __init__(self, valor: str) -> None:
        self.valor = valor
        self.consultas: list[str] = []

    def execute(self, sql: str) -> None:
        self.consultas.append(sql)

    def fetchone(self):
        return (self.valor,)

    def close(self) -> None:
        pass


class _ConexaoFalsa:
    autocommit = False

    def __init__(self, valor: str) -> None:
        self.cursor_falso = _CursorFalso(valor)
        self.desfeitas = 0

    def cursor(self):
        return self.cursor_falso

    def rollback(self) -> None:
        self.desfeitas += 1


def test_superusuario_real_e_recusado_quando_exigido(app_com_banco, monkeypatch):
    from app.models import db

    monkeypatch.setenv(VARIAVEL, "1")
    with app_com_banco.app_context():
        bruta = db.engine.raw_connection()
        try:
            with pytest.raises(PapelPrivilegiadoError):
                conferir_conexao(bruta.driver_connection)
        finally:
            bruta.close()


def test_sem_a_variavel_o_papel_administrativo_passa(app_com_banco, monkeypatch):
    """O `migrate` usa o superusuário de propósito, sem a variável ligada."""
    from app.models import db

    monkeypatch.delenv(VARIAVEL, raising=False)
    with app_com_banco.app_context():
        bruta = db.engine.raw_connection()
        try:
            conferir_conexao(bruta.driver_connection)
        finally:
            bruta.close()


def test_papel_restrito_passa_e_devolve_a_conexao_limpa(monkeypatch):
    monkeypatch.setenv(VARIAVEL, "1")
    conexao = _ConexaoFalsa("off")
    conferir_conexao(conexao)
    assert conexao.cursor_falso.consultas == ["SHOW is_superuser"]
    assert conexao.desfeitas == 1


def test_superusuario_falso_e_recusado(monkeypatch):
    monkeypatch.setenv(VARIAVEL, "1")
    with pytest.raises(PapelPrivilegiadoError):
        conferir_conexao(_ConexaoFalsa("on"))


def test_a_fabrica_liga_a_trava_ao_engine(app):
    """Sem o `instalar` em `create_app`, a trava existiria e nunca rodaria."""
    from app.models import db

    with app.app_context():
        assert event.contains(db.engine, "connect", conferir_conexao)
