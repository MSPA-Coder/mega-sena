"""Resultado estável da confirmação, independente de sessão ORM ou HTTP."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfirmationResult:
    saved_count: int
    generation_id: int | None
    replayed: bool = False


@dataclass(frozen=True)
class DeletedBet:
    id: int
    generation_id: int | None
