from __future__ import annotations

from app.generation_params import GENERATION_FILTER_KEYS, GenerationParams


def test_generation_params_centralize_bounds_and_cross_field_rules() -> None:
    params = GenerationParams.from_mapping(
        {
            "quantity": "99",
            "amount": "0",
            "even_min": "5",
            "even_max": "2",
            "sum_min": "300",
            "sum_max": "20",
            "range_min_occupied": "0",
            "range_max_per_band": "99",
        }
    )

    assert params.quantity == 15
    assert params.amount == 1
    assert params.even_min == 5
    assert params.even_max == 5
    assert (params.sum_min, params.sum_max) == (20, 300)
    assert params.range_min_occupied == 1
    assert params.range_max_per_band == 6


def test_generation_params_expose_one_canonical_filter_mapping() -> None:
    params = GenerationParams.from_mapping(
        {"even_min": "2", "sum_max": "", "consecutive_count": "abc"},
        default_quantity=7,
        default_amount=9,
    )

    assert params.quantity == 7
    assert params.amount == 9
    assert params.filters() == {"even_min": 2}
    assert tuple(params.filters(include_empty=True)) == GENERATION_FILTER_KEYS
