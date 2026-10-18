"""Configuração/reset e auditoria são confirmados ou desfeitos juntos."""

from ..audit.contracts import AuditContext
from ..audit.service import add_success
from ..extensions import db
from . import service


def update_config_values(values: dict[str, object], *, audit: AuditContext) -> dict[str, str]:
    try:
        result = service.update_config_values(values, commit=False)
        add_success(audit, action="settings.update", entity="config")
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
