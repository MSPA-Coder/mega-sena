"""Contrato da importação com o PostgreSQL real, sem fonte HTTP externa."""

from __future__ import annotations

from io import BytesIO

import pytest
from openpyxl import Workbook

from app.draws.importing import import_results_from_xlsx
from app.extensions import db
from app.models import AuditEvent, Draw, ImportBatch, ImportQuarantine

pytestmark = pytest.mark.banco


def _xlsx() -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "Concurso",
            "Data Sorteio",
            "Bola 1",
            "Bola 2",
            "Bola 3",
            "Bola 4",
            "Bola 5",
            "Bola 6",
        ]
    )
    # A ordem das dezenas é normalizada, mas fica registrada em quarentena.
    sheet.append([54321, "01/08/2026", 6, 5, 4, 3, 2, 1])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    stream.seek(0)
    return stream


def test_import_persiste_proveniencia_quarentena_e_auditoria(app_com_banco):
    with app_com_banco.app_context():
        result = import_results_from_xlsx(
            _xlsx(),
            provenance={
                "source_type": "manual_upload",
                "source_name": "resultado-oficial.xlsx",
            },
            audit={
                "actor": None,
                "context": {"route": "test", "source": "upload"},
            },
        )

        batch = ImportBatch.query.filter_by(source_name="resultado-oficial.xlsx").one()
        draw = Draw.query.filter_by(contest=54321).one()
        quarantine = ImportQuarantine.query.filter_by(import_batch_id=batch.id).one()
        event = (
            AuditEvent.query.filter_by(action="draws.import")
            .order_by(AuditEvent.id.desc())
            .first()
        )

        assert result == {"imported": 1, "updated": 0, "ignored": 0}
        assert batch.content_sha256 and len(batch.content_sha256) == 64
        assert draw.import_batch_id == batch.id
        assert quarantine.reason == "numbers_order_normalized"
        assert event is not None
        assert event.context["imported"] == 1
        assert event.context["quarantined"] == 1

        # A fixture de PostgreSQL é compartilhada pela sessão do pytest; não
        # deixe esta prova de commit alterar o estado observado pelos testes
        # de constraints que vêm depois.
        db.session.delete(draw)
        if event is not None:
            db.session.delete(event)
        db.session.delete(batch)
        db.session.commit()
