"""Cobertura de prêmios e opções de geração, com oráculos combinatórios."""
from itertools import chain, repeat
from math import comb

from app.bets import service
from app.bets.combinatorics import count_prize_coverage


def test_coverage_counts_distinct_draws_for_overlapping_bets():
    first = [1, 2, 3, 4, 5, 6]
    second = [1, 2, 3, 4, 7, 8]
    result = count_prize_coverage([first, second])
    assert result is not None
    assert result[4] == 41186
    assert result[6] == 2
    assert result[4] > result[5] > result[6]
    assert count_prize_coverage([first, first]) == count_prize_coverage([first])


def test_coverage_for_expanded_bet_and_limit():
    bet = list(range(1, 8))
    result = count_prize_coverage([bet])
    assert result is not None
    assert result[4] == sum(comb(7, k) * comb(53, 6-k) for k in (4, 5, 6))
    assert result[5] == comb(7, 5) * 53 + comb(7, 6)
    assert result[6] == comb(7, 6)
    assert count_prize_coverage([list(range(1, 21))]) is None


def test_can_include_previous_results(monkeypatch):
    previous = [1, 2, 3, 4, 5, 6]
    alternative = [10, 11, 12, 13, 14, 15]
    monkeypatch.setattr(service, "all_draw_numbers", lambda: [previous])
    monkeypatch.setattr(service, "_secure_random_candidate", lambda _: previous)
    assert service.generate_bets(6, 1, exclude_previous=False)[0].numbers == previous
    candidates = iter([previous, alternative])
    monkeypatch.setattr(service, "_secure_random_candidate", lambda _: next(candidates))
    assert service.generate_bets(6, 1, exclude_previous=True)[0].numbers == alternative


def test_prioritization_prefers_less_overlapping_candidate(monkeypatch):
    first = [1, 2, 3, 4, 5, 6]
    overlapping = [1, 2, 3, 4, 7, 8]
    distinct = [10, 11, 12, 13, 14, 15]
    candidates = iter(chain([first, overlapping, distinct], repeat(overlapping)))
    monkeypatch.setattr(service, "_secure_random_candidate", lambda _: next(candidates))
    bets = service.generate_bets(6, 2, exclude_previous=False, prioritize_coverage=True)
    assert [bet.numbers for bet in bets] == [first, distinct]
