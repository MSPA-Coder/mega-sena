"""Casos de uso de consulta dos concursos."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import Draw


@dataclass(frozen=True, slots=True)
class ContestSearchResult:
    pagination: Any
    winners_only: bool
    consecutive_count: int | None
    even_count: int | None
    active_filters: tuple[str, ...]
    summary: str


def count_draws() -> int:
    return Draw.query.count()


def search_contests(
    *,
    page: int,
    winners_only: bool,
    consecutive_count: int | None,
    even_count: int | None,
) -> ContestSearchResult:
    """Consulta concursos e devolve os metadados necessarios para a pagina."""
    page = max(1, page)
    query = Draw.query
    active_filters: list[str] = []
    if winners_only:
        query = query.filter(Draw.winners_6 > 0)
    if consecutive_count is not None:
        consecutive_count = max(0, min(consecutive_count, 6))
        query = query.filter(Draw.consecutive_count == consecutive_count)
        active_filters.append(f"maior sequência de números consecutivos = {consecutive_count}")
    if even_count is not None:
        even_count = max(0, min(even_count, 6))
        query = query.filter(Draw.even_count == even_count)
        active_filters.append(f"quantidade de números pares = {even_count}")

    pagination = query.order_by(Draw.contest.desc()).paginate(page=page, per_page=50, error_out=False)
    if winners_only:
        summary = (
            f"{pagination.total} concurso com acertadores na Mega Sena encontrado."
            if pagination.total == 1
            else f"{pagination.total} concursos com acertadores na Mega Sena encontrados."
        )
    elif active_filters:
        summary = (
            f"{pagination.total} concurso encontrado."
            if pagination.total == 1
            else f"{pagination.total} concursos encontrados."
        )
    else:
        summary = (
            f"{pagination.total} concurso importado."
            if pagination.total == 1
            else f"{pagination.total} concursos importados."
        )
    return ContestSearchResult(
        pagination=pagination,
        winners_only=winners_only,
        consecutive_count=consecutive_count,
        even_count=even_count,
        active_filters=tuple(active_filters),
        summary=summary,
    )
