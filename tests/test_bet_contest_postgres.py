from io import BytesIO

import pytest
from openpyxl import Workbook

from app.audit.contracts import AuditContext
from app.bets.commands import confirm_generated_bets
from app.bets.service import list_recent_generations_with_bets
from app.draws.importing import import_results_from_xlsx
from app.extensions import db
from app.models import AuditEvent, Draw, GeneratedBet

pytestmark = pytest.mark.banco


def spreadsheet(numbers):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Concurso", *(f"Bola {n}" for n in range(1, 7))])
    sheet.append([87654, *numbers])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    stream.seek(0)
    return stream


def test_import_checks_matching_contest_and_reimport_updates_result(app_com_banco):
    with app_com_banco.app_context():
        audit = AuditContext(None)
        first = confirm_generated_bets(6, ["1,2,3,4,5,20"], audit=audit, contest=87654)
        other = confirm_generated_bets(6, ["1,2,3,4,5,20"], audit=audit, contest=87655)
        assert first.generation_id != other.generation_id
        assert confirm_generated_bets(6, ["1,2,3,4,5,20"], audit=audit, contest=87654).replayed
        try:
            result = import_results_from_xlsx(spreadsheet([1, 2, 3, 4, 5, 6]))
            assert result["winning_bets"] == 1
            groups = {g["generation_id"]: g for g in list_recent_generations_with_bets()}
            bet = groups[first.generation_id]["bets"][0]
            assert bet.hit_count == 5 and bet.winning_numbers == {1, 2, 3, 4, 5}
            assert groups[other.generation_id]["bets"][0].hit_count is None
            result = import_results_from_xlsx(spreadsheet([21, 22, 23, 24, 25, 26]))
            assert "winning_bets" not in result
            groups = {g["generation_id"]: g for g in list_recent_generations_with_bets()}
            assert groups[first.generation_id]["bets"][0].winning_numbers == set()
        finally:
            GeneratedBet.query.filter(GeneratedBet.generation_id.in_([first.generation_id, other.generation_id])).delete(synchronize_session=False)
            Draw.query.filter_by(contest=87654).delete()
            AuditEvent.query.filter(AuditEvent.entity_id.in_([str(first.generation_id), str(other.generation_id)]), AuditEvent.action == "bets.save").delete(synchronize_session=False)
            db.session.commit()


def test_migration_associates_existing_bets_and_can_be_reversed(app_com_banco):
    from flask_migrate import downgrade, upgrade
    from sqlalchemy import text

    with app_com_banco.app_context():
        db.session.remove()
        downgrade(revision="20261021_0008_session_epoch")
        try:
            db.session.execute(text(
                "INSERT INTO generated_bets (generation_id, numbers_csv, quantity, score, created_at) "
                "VALUES (987654, '1,2,3,4,5,6', 6, 0, now())"
            ))
            db.session.commit()
            upgrade()
            assert GeneratedBet.query.filter_by(generation_id=987654).one().contest == 3076
        finally:
            db.session.rollback()
            db.session.execute(text("DELETE FROM generated_bets WHERE generation_id = 987654"))
            db.session.commit()
            db.session.remove()
            upgrade()
