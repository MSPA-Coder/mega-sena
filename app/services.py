from __future__ import annotations

from typing import BinaryIO, Iterable
from pathlib import Path

from .generation_params import GENERATION_FILTER_KEYS
from .bets import service as _betting
from .bets.combinatorics import (
    build_combination_report,
    calculate_individual_filter_targets,
    count_draws_matching_filters,
    count_possible_draw_combinations,
)
from .bets.service import (
    _passes_generation_filters,
    generate_closure_bets,
    list_recent_generations,
    list_recent_generations_with_bets,
)
from .core.numbers import (
    count_consecutive_numbers,
    count_even_numbers,
    count_occupied_range_bands,
    draw_parameters,
    format_int,
    format_percent,
    max_range_band_count,
    range_band_counts,
)
from .draws import importing as _importing
from .draws.importing import MAX_IMPORT_ROWS, MAX_XLSX_ARCHIVE_FILES, MAX_XLSX_COMPRESSION_RATIO
from .draws.statistics import (
    all_draw_numbers,
    build_recent_frequency,
    build_stats,
    ensure_draw_parameters_current,
    refresh_draw_parameters,
)
from .settings.service import (
    CONFIG_LIMITS,
    DEFAULT_CONFIG,
    ensure_default_config,
    get_config_values,
    get_generation_defaults,
    update_config_values,
)

__all__ = (
    "CONFIG_LIMITS",
    "DEFAULT_CONFIG",
    "GENERATION_FILTER_KEYS",
    "MAX_IMPORT_ROWS",
    "MAX_SAVED_BETS",
    "MAX_XLSX_ARCHIVE_FILES",
    "MAX_XLSX_COMPRESSION_RATIO",
    "MAX_XLSX_UNCOMPRESSED_BYTES",
    "_passes_generation_filters",
    "all_draw_numbers",
    "build_combination_report",
    "build_recent_frequency",
    "build_stats",
    "calculate_individual_filter_targets",
    "count_consecutive_numbers",
    "count_draws_matching_filters",
    "count_even_numbers",
    "count_occupied_range_bands",
    "count_possible_draw_combinations",
    "draw_parameters",
    "ensure_default_config",
    "ensure_draw_parameters_current",
    "format_int",
    "format_percent",
    "generate_bets",
    "generate_closure_bets",
    "get_config_values",
    "get_generation_defaults",
    "import_results_from_xlsx",
    "list_recent_generations",
    "list_recent_generations_with_bets",
    "max_range_band_count",
    "range_band_counts",
    "refresh_draw_parameters",
    "save_generated_bets",
    "update_config_values",
)

MAX_SAVED_BETS = _betting.MAX_SAVED_BETS
MAX_XLSX_UNCOMPRESSED_BYTES = _importing.MAX_XLSX_UNCOMPRESSED_BYTES
_secure_random_candidate = _betting._secure_random_candidate


def import_results_from_xlsx(source: str | Path | BinaryIO) -> dict[str, int]:
    _importing.MAX_XLSX_UNCOMPRESSED_BYTES = MAX_XLSX_UNCOMPRESSED_BYTES
    return _importing.import_results_from_xlsx(source)


def generate_bets(
    quantity: int,
    amount: int,
    persist: bool = True,
    filters: dict | None = None,
):
    _betting._secure_random_candidate = _secure_random_candidate
    return _betting.generate_bets(quantity=quantity, amount=amount, persist=persist, filters=filters)


def save_generated_bets(quantity: int, bets: Iterable[str]) -> tuple[int, int | None]:
    _betting.MAX_SAVED_BETS = MAX_SAVED_BETS
    return _betting.save_generated_bets(quantity, bets)
