"""MS-01: `SECRET_KEY` do ambiente é um caminho de compatibilidade, e agora
é audível.

Até 02/09/2026 esse fallback (`os.environ.get("SECRET_KEY")`, usado só quando
nem `app.config["SECRET_KEY"]` nem `SECRET_KEY_FILE` resolvem) ficava
silencioso -- indistinguível, no log, do caminho normal por arquivo Docker
secret. `.env.docker` também guardava `POSTGRES_PASSWORD` e `SECRET_KEY` em
texto claro, os MESMOS valores já em `.secrets/`; removidos com
`scripts/provision_secrets.ps1 -RemoveLegacyValues` (fora do escopo desta
suíte -- mexe em arquivo local, não em código).
"""

from __future__ import annotations

import logging

from app import create_app

_CONFIG_SEM_CHAVE = {
    "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://test:test@localhost:5432/test",
    "TESTING": True,
}


def test_secret_key_do_ambiente_registra_warning(monkeypatch, caplog):
    monkeypatch.delenv("SECRET_KEY_FILE", raising=False)
    monkeypatch.setenv("SECRET_KEY", "chave-via-ambiente-para-teste")

    with caplog.at_level(logging.WARNING):
        app = create_app(dict(_CONFIG_SEM_CHAVE))

    assert app.config["SECRET_KEY"] == "chave-via-ambiente-para-teste"
    assert any("SECRET_KEY_FILE" in registro.message for registro in caplog.records), (
        "a resolução por variável de ambiente devia registrar WARNING "
        "identificando o caminho de compatibilidade"
    )


def test_secret_key_de_arquivo_nao_registra_warning(monkeypatch, tmp_path, caplog):
    arquivo = tmp_path / "secret_key"
    arquivo.write_text("chave-de-arquivo-para-teste", encoding="utf-8")
    monkeypatch.setenv("SECRET_KEY_FILE", str(arquivo))
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with caplog.at_level(logging.WARNING):
        app = create_app(dict(_CONFIG_SEM_CHAVE))

    assert app.config["SECRET_KEY"] == "chave-de-arquivo-para-teste"
    assert not caplog.records, "o caminho normal (por arquivo) não deve registrar WARNING"
