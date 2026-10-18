"""Identidade e metadados mínimos de um comando, sem depender de HTTP."""

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuditContext:
    actor_id: int | None = None
    context: Mapping[str, str] = field(default_factory=dict)
