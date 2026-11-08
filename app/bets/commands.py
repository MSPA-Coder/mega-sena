"""Comandos: aposta, lock e evento de sucesso pertencem ao mesmo commit."""

from collections.abc import Iterable
from math import comb
from uuid import UUID, uuid4

from ..audit.contracts import AuditContext
from ..audit.service import add_success
from ..extensions import db
from ..models import GeneratedBet
from .contracts import ConfirmationResult, DeletedBet
from .service import (
    _diversity_score,
    prepare_closure_bets,
    prepare_generated_bets,
    stage_bet_batch,
    stage_delete_bet,
)


def _confirm(prepared: list[GeneratedBet], audit: AuditContext, contest: int | None = None,
             token: str | None = None) -> ConfirmationResult:
    try:
        try:
            token = str(UUID(token)) if token else str(uuid4())
        except (ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError("Identificador de confirmação inválido.") from exc
        for bet in prepared:
            bet.contest = contest
        result = stage_bet_batch(prepared, token, audit.actor_id)
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
    quantity: int, bets: Iterable[str], *, audit: AuditContext, contest: int | None = None,
    token: str | None = None,
) -> ConfirmationResult:
    return _confirm(
        prepare_generated_bets(quantity, bets, recompute_diversity=True), audit, contest, token
    )


def confirm_closure_bets(numbers: Iterable[int], *, audit: AuditContext, contest: int | None = None,
                         token: str | None = None) -> ConfirmationResult:
    return _confirm(prepare_closure_bets(numbers), audit, contest, token)


def recalcular_scores_zerados(*, aplicar: bool) -> tuple[int, int]:
    """Corrige apostas gravadas com diversidade zero antes do commit 5d7fe46.

    Só entram gerações inteiras com score zero. A primeira aposta de uma geração
    aleatória sempre vale 1, então uma geração toda zerada é o sintoma do defeito.
    Fechamento fica de fora: nele o zero é o valor correto. Fechamento é o conjunto
    completo das combinações das suas dezenas, e assim é reconhecido aqui.
    Devolve (gerações afetadas, apostas afetadas). Sem `aplicar`, nada é gravado.
    """
    bets = db.session.scalars(
        db.select(GeneratedBet)
        .where(GeneratedBet.generation_id.is_not(None))
        .order_by(GeneratedBet.id)
    ).all()
    geracoes: dict[tuple[int, int], list[GeneratedBet]] = {}
    for bet in bets:
        geracoes.setdefault((bet.owner_id, bet.generation_id), []).append(bet)

    afetadas = apostas = 0
    try:
        for lote in geracoes.values():
            if any(bet.score != 0 for bet in lote):
                continue
            dezenas = {numero for bet in lote for numero in bet.numbers}
            if len(lote) == comb(len(dezenas), lote[0].quantity):
                continue
            afetadas += 1
            apostas += len(lote)
            anteriores: list[list[int]] = []
            for bet in lote:
                bet.score = round(_diversity_score(bet.numbers, anteriores), 4)
                anteriores.append(bet.numbers)
        if aplicar:
            db.session.commit()
        else:
            db.session.rollback()
    except Exception:
        db.session.rollback()
        raise
    return afetadas, apostas


def delete_saved_bet(bet_id: int, *, audit: AuditContext) -> DeletedBet:
    """Apaga uma aposta de quem está agindo: o dono é sempre o autor (ADR 0004)."""
    try:
        if audit.actor_id is None:
            raise RuntimeError("A aposta salva não foi encontrada.")
        bet = stage_delete_bet(bet_id, audit.actor_id)
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
