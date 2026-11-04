"""Configuração/reset e auditoria são confirmados ou desfeitos juntos."""

from ..audit.contracts import AuditContext
from ..audit.service import add_success
from ..extensions import db
from . import service


def update_generation_values(
    user_id: int, values: dict[str, object], *, audit: AuditContext
) -> dict[str, str]:
    """Grava os padrões de geração da própria conta (ADR 0004)."""
    try:
        result = service.update_generation_values(user_id, values, commit=False)
        add_success(audit, action="settings.update", entity="user_config", entity_id=user_id)
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise


def update_results_source_url(value: object, *, audit: AuditContext) -> str:
    """Grava o endereço da planilha de resultados, que vale para todos."""
    try:
        result = service.update_results_source_url(value, commit=False)
        add_success(audit, action="settings.update_system", entity="config")
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise


def reset_all_data(*, audit: AuditContext) -> tuple[int, int]:
    try:
        draws, bets = service.reset_all_data(commit=False)
        add_success(
            audit,
            action="data.reset",
            entity="draws_and_generated_bets",
            details={"draw_count": draws, "bet_count": bets},
        )
        db.session.commit()
        return draws, bets
    except Exception:
        db.session.rollback()
        raise
