"""Serviço pequeno para registrar eventos de auditoria sem dados sensíveis."""

from __future__ import annotations

from typing import Any

from ..extensions import db
from ..models import AuditEvent, User


def record_event(
    *,
    action: str,
    entity: str,
    entity_id: str | int | None = None,
    actor: User | None = None,
    success: bool,
    context: dict[str, Any] | None = None,
    commit: bool = True,
) -> AuditEvent:
    """Adiciona um evento já sanitizado à transação corrente.

    O chamador nunca deve enviar senha, token, conteúdo de planilha ou dados
    completos de formulários. `context` existe para metadados operacionais
    mínimos, como IP, rota e origem da importação. Por compatibilidade, o
    padrão ainda confirma o evento; operações compostas podem passar
    ``commit=False`` e confirmar tudo atomicamente ao final.
    """
    event = AuditEvent(
        actor_user_id=actor.id if actor is not None else None,
        action=action,
        entity=entity,
        entity_id=None if entity_id is None else str(entity_id),
        success=success,
        context=context or {},
    )
    db.session.add(event)
    if commit:
        db.session.commit()
    return event
