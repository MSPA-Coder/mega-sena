from __future__ import annotations

import math

import pytest

from app.bets import service


@pytest.mark.parametrize("number_count", [6, 7, 10, 20])
def test_closure_produces_every_six_number_combination(number_count):
    numbers = range(1, number_count + 1)

    bets = service.generate_closure_bets(numbers)

    assert service.count_closure_bets(numbers) == math.comb(number_count, 6)
    assert len(bets) == math.comb(number_count, 6)
    assert len({bet.numbers_csv for bet in bets}) == len(bets)


@pytest.mark.parametrize(
    ("numbers", "message"),
    [
        ([1, 2, 3, 4, 5], "pelo menos 6 dezenas distintas"),
        (range(1, 22), "no máximo 20 dezenas"),
        ([1, 1, 2, 3, 4, 5, 5], "pelo menos 6 dezenas distintas"),
        ([0, 1, 2, 3, 4, 5], "entre 1 e 60"),
        ([1, 2, 3, 4, 5, 61], "entre 1 e 60"),
    ],
)
def test_closure_validates_size_distinctness_and_number_bounds(numbers, message):
    with pytest.raises(RuntimeError, match=message):
        service.generate_closure_bets(numbers)


def test_closure_normalizes_repeated_input_when_six_distinct_numbers_remain():
    bets = service.generate_closure_bets([6, 5, 4, 3, 2, 1, 1])

    assert [bet.numbers_csv for bet in bets] == ["1,2,3,4,5,6"]
