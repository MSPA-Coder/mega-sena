"""Comandos: aposta, lock e evento de sucesso pertencem ao mesmo commit."""

from collections.abc import Iterable

from ..audit.contracts import AuditContext
from ..audit.service import add_success
from ..extensions import db
from ..models import GeneratedBet
from .contracts import ConfirmationResult, DeletedBet
from .service import prepare_closure_bets, prepare_generated_bets, stage_bet_batch, stage_delete_bet


def _confirm(prepared: list[GeneratedBet], audit: AuditContext) -> ConfirmationResult:
    try:
        result = stage_bet_batch(prepared)
        # Replay recupera o lote; não anuncia uma segunda criação na auditoria.
        if result.saved_count and not result.replayed:
            add_success(
                audit,
                action="bets.save",
                entity="generated_bet_batch",
                entity_id=result.generation_id,
                details={"saved_count": result.saved_count},
            )
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise


def confirm_generated_bets(
    quantity: int, bets: Iterable[str], *, audit: AuditContext
) -> ConfirmationResult:
    return _confirm(prepare_generated_bets(quantity, bets), audit)


def confirm_closure_bets(numbers: Iterable[int], *, audit: AuditContext) -> ConfirmationResult:
    return _confirm(prepare_closure_bets(numbers), audit)


def delete_saved_bet(bet_id: int, *, audit: AuditContext) -> DeletedBet:
    try:
        bet = stage_delete_bet(bet_id)
        result = DeletedBet(bet.id, bet.generation_id)
        add_success(
            audit,
            action="bets.delete",
            entity="generated_bet",
            entity_id=bet.id,
            details={"generation_id": bet.generation_id},
        )
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise
