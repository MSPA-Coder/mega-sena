from __future__ import annotations

from itertools import chain, repeat

from app.bets import service
from app.bets.criteria import GenerationCriteria


def test_generation_criteria_normalizes_clamps_and_resolves_inverted_ranges():
    criteria = GenerationCriteria.from_mapping(
        {
            "quantity": "-9",
            "amount": "999",
            "consecutive_count": "99",
            "even_min": "5",
            "even_max": "2",
            "sum_min": "300",
            "sum_max": "100",
            "range_min_occupied": "0",
            "range_max_per_band": "99",
        }
    )

    assert criteria == GenerationCriteria(
        quantity=6,
        amount=100,
        consecutive_count=6,
        even_min=5,
        even_max=5,
        sum_min=100,
        sum_max=300,
        range_min_occupied=1,
        range_max_per_band=6,
    )
    assert GenerationCriteria.from_mapping(
        {"quantity": " ", "amount": True},
        default_quantity=12,
        default_amount=8,
    ) == GenerationCriteria(quantity=12, amount=8)


def test_generation_criteria_applies_inclusive_filter_boundaries():
    criteria = GenerationCriteria(
        consecutive_count=2,
        even_min=3,
        even_max=3,
        sum_min=125,
        sum_max=125,
        range_min_occupied=5,
        range_max_per_band=2,
    )

    assert criteria.matches_candidate([1, 2, 14, 25, 36, 47])
    assert not GenerationCriteria(sum_min=126).matches_candidate([1, 2, 14, 25, 36, 47])
    assert not GenerationCriteria(sum_max=124).matches_candidate([1, 2, 14, 25, 36, 47])
    assert not GenerationCriteria(even_min=4).matches_candidate([1, 2, 14, 25, 36, 47])
    assert not GenerationCriteria(consecutive_count=1).matches_candidate(
        [1, 2, 14, 25, 36, 47]
    )


def test_expanded_bets_are_checked_by_the_extreme_internal_six_number_bets():
    criteria = GenerationCriteria(
        even_min=3,
        even_max=4,
        sum_min=171,
        sum_max=230,
        range_min_occupied=5,
        range_max_per_band=2,
    )

    assert criteria.matches_candidate([1, 12, 23, 34, 45, 56, 60])
    assert not GenerationCriteria(even_max=4).matches_candidate(
        [1, 2, 3, 12, 22, 32, 42]
    )
    assert not GenerationCriteria(sum_min=22).matches_candidate([1, 2, 3, 4, 5, 6, 7])
    assert not GenerationCriteria(range_min_occupied=3).matches_candidate(
        [1, 2, 3, 4, 5, 11, 21]
    )


def test_generation_is_in_memory_skips_draws_and_respects_filters_and_diversity(
    monkeypatch,
):
    drawn = [1, 2, 3, 4, 5, 6]
    accepted_first = [1, 12, 23, 34, 45, 56]
    too_similar = [1, 12, 23, 34, 45, 57]
    filtered_out = [2, 4, 6, 8, 10, 12]
    accepted_second = [2, 13, 24, 35, 46, 57]
    candidates = iter(
        chain(
            [drawn, accepted_first, too_similar, filtered_out, accepted_second],
            repeat(accepted_second),
        )
    )

    monkeypatch.setattr(service, "all_draw_numbers", lambda: [drawn])
    monkeypatch.setattr(service, "_secure_random_candidate", lambda quantity: next(candidates))

    def must_not_persist(_bets):
        raise AssertionError("generate_bets must not persist before confirmation")

    monkeypatch.setattr(service, "_persist_bet_batch", must_not_persist)

    bets = service.generate_bets(
        6,
        2,
        {"even_min": 3, "even_max": 3, "sum_min": 100, "range_min_occupied": 5},
    )

    assert [bet.numbers for bet in bets] == [accepted_first, accepted_second]
    assert len(set(accepted_first) & set(accepted_second)) <= 4
