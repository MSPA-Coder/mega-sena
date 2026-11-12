"""Propriedades da implantação declaradas no `compose.yaml`.

O arquivo é carregado como YAML e conferido pelo valor (docs/TESTES.md, T4):
reordenar chaves ou reescrever comentários não reprova nada aqui, e um serviço
novo sem endurecimento aparece pelo nome.
"""

from __future__ import annotations

from pathlib import Path

import yaml

COMPOSE = Path(__file__).resolve().parent.parent / "compose.yaml"


def _servicos() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]


def test_todo_servico_roda_sem_privilegios_extras() -> None:
    """Nenhum contêiner ganha escrita na raiz, capability ou escalada.

    O banco pode gravar PGDATA pelo volume, e só; o resto grava em tmpfs.
    """
    fora = {
        nome: campo
        for nome, servico in _servicos().items()
        for campo, ok in (
            ("read_only", servico.get("read_only") is True),
            ("cap_drop", "ALL" in servico.get("cap_drop", [])),
            ("security_opt", "no-new-privileges:true" in servico.get("security_opt", [])),
            ("pids_limit", bool(servico.get("pids_limit"))),
        )
        if not ok
    }
    assert not fora, f"serviços sem endurecimento: {fora}"


def test_producao_nao_publica_a_porta_do_postgres() -> None:
    """Em produção só o app fala com o banco: o `compose.release.yaml` zera as portas.

    O `compose.yaml` publica o banco no loopback para ferramentas do
    desenvolvimento local; o `deploy.sh` soma o override e a porta some.
    """

    class Leitor(yaml.SafeLoader):
        pass

    Leitor.add_constructor("!reset", lambda loader, no: [])
    release = yaml.load(  # noqa: S506 - Leitor herda de SafeLoader
        (COMPOSE.parent / "compose.release.yaml").read_text(encoding="utf-8"), Loader=Leitor
    )
    assert release["services"]["postgres"]["ports"] == []
