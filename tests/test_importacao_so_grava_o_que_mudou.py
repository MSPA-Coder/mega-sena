"""A importação só regrava o concurso cujo dado mudou.

Antes, o lote novo era gravado em toda linha existente, mesmo "ignorada": cada
importação reescrevia a tabela inteira. O teste mede pelo `xmin` da linha (muda
a cada UPDATE) e confere que `import_batch_id` continua sendo o lote que
forneceu a versão atual.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from openpyxl import Workbook
from sqlalchemy import delete, text

from app.draws.importing import import_results_from_xlsx
from app.extensions import db
from app.models import AuditEvent, Draw, ImportBatch, ImportQuarantine

pytestmark = pytest.mark.banco

CONCURSOS = (54401, 54402, 54403)


def _xlsx(dezenas_do_ultimo: tuple[int, ...] = (6, 7, 8, 9, 10, 11)) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Concurso", "Data Sorteio", *(f"Bola {i}" for i in range(1, 7))])
    sheet.append([CONCURSOS[0], "01/08/2026", 1, 2, 3, 4, 5, 6])
    sheet.append([CONCURSOS[1], "02/08/2026", 7, 8, 9, 10, 11, 12])
    sheet.append([CONCURSOS[2], "03/08/2026", *dezenas_do_ultimo])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    stream.seek(0)
    return stream


def _importar(nome: str, planilha: BytesIO) -> dict[str, int]:
    return import_results_from_xlsx(
        planilha,
        provenance={"source_type": "manual_upload", "source_name": nome},
        audit={"actor": None, "context": {"route": "test", "source": "upload"}},
    )


def _estado() -> dict[int, tuple[str, int | None]]:
    linhas = db.session.execute(
        text(
            "SELECT contest, xmin::text, import_batch_id FROM draws"
            " WHERE contest = ANY(:c) ORDER BY contest"
        ),
        {"c": list(CONCURSOS)},
    ).all()
    db.session.rollback()
    return {contest: (xmin, lote) for contest, xmin, lote in linhas}


def _lote(nome: str) -> int:
    return ImportBatch.query.filter_by(source_name=nome).one().id


@pytest.fixture
def limpeza(app_com_banco):
    yield
    with app_com_banco.app_context():
        db.session.rollback()
        db.session.execute(delete(Draw).where(Draw.contest.in_(CONCURSOS)))
        lotes = [
            b.id for b in ImportBatch.query.filter(ImportBatch.source_name.like("so-muda-%"))
        ]
        db.session.execute(
            delete(ImportQuarantine).where(ImportQuarantine.import_batch_id.in_(lotes))
        )
        db.session.execute(delete(AuditEvent).where(AuditEvent.action == "draws.import"))
        db.session.execute(delete(ImportBatch).where(ImportBatch.id.in_(lotes)))
        db.session.commit()


def test_repetir_a_importacao_nao_toca_nas_linhas(app_com_banco, limpeza):
    with app_com_banco.app_context():
        assert _importar("so-muda-1", _xlsx()) == {"imported": 3, "updated": 0, "ignored": 0}
        primeiro = _lote("so-muda-1")
        antes = _estado()
        assert {lote for _, lote in antes.values()} == {primeiro}

        assert _importar("so-muda-2", _xlsx()) == {"imported": 0, "updated": 0, "ignored": 3}

        depois = _estado()
        assert depois == antes, "nenhuma linha ignorada pode ser regravada"


def test_so_a_linha_que_mudou_e_regravada_e_leva_o_lote_novo(app_com_banco, limpeza):
    with app_com_banco.app_context():
        _importar("so-muda-1", _xlsx())
        primeiro = _lote("so-muda-1")
        antes = _estado()

        resultado = _importar("so-muda-3", _xlsx(dezenas_do_ultimo=(6, 7, 8, 9, 10, 12)))
        assert resultado == {"imported": 0, "updated": 1, "ignored": 2}

        depois = _estado()
        terceiro = _lote("so-muda-3")
        alteradas = [c for c in CONCURSOS if depois[c][0] != antes[c][0]]
        assert alteradas == [CONCURSOS[2]]
        assert depois[CONCURSOS[0]][1] == primeiro
        assert depois[CONCURSOS[1]][1] == primeiro
        assert depois[CONCURSOS[2]][1] == terceiro
