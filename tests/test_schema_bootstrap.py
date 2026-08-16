"""O grafo de migracoes esta integro e tem uma cabeca so.

Nao aplica migracoes: isso e verificacao manual obrigatoria contra PostgreSQL
vazio, como a base registra. O que este arquivo protege e a classe de erro que
a consolidacao de baselines introduz e que o bootstrap manual so revela tarde
-- duas cabecas, revisao duplicada, elo quebrado -- e que aqui custa
milissegundos.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

VERSOES = Path(__file__).resolve().parent.parent / "migrations" / "versions"


def _revisoes() -> dict[str, str | None]:
    """Mapeia revision -> down_revision lendo os arquivos, sem importar Alembic."""
    encontradas: dict[str, str | None] = {}
    for arquivo in VERSOES.glob("*.py"):
        texto = arquivo.read_text(encoding="utf-8")
        revisao = re.search(r"^revision\s*=\s*[\"']([^\"']+)[\"']", texto, re.MULTILINE)
        anterior = re.search(
            r"^down_revision\s*=\s*(?:[\"']([^\"']+)[\"']|None)", texto, re.MULTILINE
        )
        assert revisao, f"{arquivo.name} nao declara `revision`"
        assert anterior, f"{arquivo.name} nao declara `down_revision`"
        chave = revisao.group(1)
        assert chave not in encontradas, f"revision duplicada: {chave}"
        encontradas[chave] = anterior.group(1)
    return encontradas


def test_existem_migracoes():
    assert _revisoes(), "nenhuma migracao encontrada em migrations/versions"


def test_uma_unica_base():
    revisoes = _revisoes()
    bases = [rev for rev, anterior in revisoes.items() if anterior is None]
    assert len(bases) == 1, f"esperava uma baseline, encontrou {bases}"


def test_uma_unica_cabeca():
    revisoes = _revisoes()
    referenciadas = {anterior for anterior in revisoes.values() if anterior}
    cabecas = sorted(set(revisoes) - referenciadas)
    assert len(cabecas) == 1, f"esperava uma cabeca, encontrou {cabecas}"


def test_todo_elo_aponta_para_revisao_existente():
    revisoes = _revisoes()
    for revisao, anterior in revisoes.items():
        if anterior is not None:
            assert anterior in revisoes, f"{revisao} aponta para {anterior}, que nao existe"


def test_cadeia_alcanca_a_base_sem_ciclo():
    revisoes = _revisoes()
    referenciadas = {anterior for anterior in revisoes.values() if anterior}
    cabeca = next(iter(set(revisoes) - referenciadas))
    visitadas: set[str] = set()
    atual: str | None = cabeca
    while atual is not None:
        if atual in visitadas:
            pytest.fail(f"ciclo no grafo de migracoes em {atual}")
        visitadas.add(atual)
        atual = revisoes[atual]
    assert visitadas == set(revisoes), "ha revisoes fora da cadeia principal"


def test_factory_exige_chave_secreta_sem_inicializar_extensoes(monkeypatch):
    """Ausência de segredo falha antes de qualquer possível conexão.

    A URI é propositalmente plausível, mas não alcançável: o contrato testado é
    não haver fallback de `SECRET_KEY`, nem inicialização de extensão antes da
    validação. Assim o teste não toca PostgreSQL nem configuração real.
    """
    from app import create_app
    from app.extensions import db

    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY_FILE", raising=False)

    def nao_deve_inicializar(*args, **kwargs):
        pytest.fail("a configuração inválida chegou à inicialização do banco")

    monkeypatch.setattr(db, "init_app", nao_deve_inicializar)

    with pytest.raises(RuntimeError, match="SECRET_KEY é obrigatória"):
        create_app(
            {"SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://test:test@localhost:5432/test"}
        )


def test_factory_exige_url_do_banco_sem_inicializar_extensoes(monkeypatch):
    """Não há URL de banco implícita que o bootstrap possa usar por engano."""
    from app import create_app
    from app.extensions import db

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.delenv("DB_USER", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.delenv("DB_PASSWORD_FILE", raising=False)

    def nao_deve_inicializar(*args, **kwargs):
        pytest.fail("a configuração inválida chegou à inicialização do banco")

    monkeypatch.setattr(db, "init_app", nao_deve_inicializar)

    with pytest.raises(RuntimeError, match="DB_HOST é obrigatório"):
        create_app({"SECRET_KEY": "chave-isolada-de-teste"})


def test_factory_le_chave_secreta_de_arquivo_temporario(tmp_path, monkeypatch):
    """O caminho Docker secret funciona sem ler nenhum segredo da máquina."""
    from app import create_app

    arquivo = tmp_path / "secret_key.txt"
    arquivo.write_text("chave-isolada-de-arquivo", encoding="utf-8")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("SECRET_KEY_FILE", str(arquivo))

    app = create_app(
        {"SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://test:test@localhost:5432/test"}
    )

    assert app.config["SECRET_KEY"] == "chave-isolada-de-arquivo"


def test_url_do_banco_e_montada_com_senha_de_arquivo_temporario(tmp_path, monkeypatch):
    """O Compose não precisa propagar a senha em DATABASE_URL."""
    from app import _database_uri_from_environment

    arquivo = tmp_path / "postgres_password.txt"
    arquivo.write_text("senha-isolada-de-arquivo", encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "postgres-teste")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "mega_sena_teste")
    monkeypatch.setenv("DB_USER", "usuario_teste")
    monkeypatch.setenv("DB_PASSWORD_FILE", str(arquivo))

    assert _database_uri_from_environment().startswith("postgresql+psycopg://")


def test_url_do_banco_exige_arquivo_de_senha_sem_url_direta(monkeypatch):
    """Não existe senha padrão para um bootstrap local acidental."""
    from app import _database_uri_from_environment

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_PASSWORD_FILE", raising=False)
    monkeypatch.setenv("DB_HOST", "postgres-teste")
    monkeypatch.setenv("DB_USER", "usuario_teste")
    monkeypatch.setenv("DB_NAME", "mega_sena_teste")

    with pytest.raises(RuntimeError, match="DB_PASSWORD_FILE é obrigatório"):
        _database_uri_from_environment()
