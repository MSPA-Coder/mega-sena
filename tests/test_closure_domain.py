from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from app.bets import service
from app.models import GeneratedBet


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


class _ScalarResult:
    def scalar_one(self):
        return 41


class _RecordingSession:
    def __init__(self, *, fail_commit: bool = False):
        self.fail_commit = fail_commit
        self.added = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def execute(self, _statement):
        return _ScalarResult()

    def add_all(self, bets):
        self.added.extend(bets)

    def commit(self):
        self.commit_calls += 1
        if self.fail_commit:
            raise RuntimeError("commit failed")

    def rollback(self):
        self.rollback_calls += 1
        self.added.clear()


def test_bet_batch_commits_once_and_assigns_one_generation(monkeypatch):
    session = _RecordingSession()
    monkeypatch.setattr(service, "db", SimpleNamespace(session=session))
    bets = [GeneratedBet(quantity=6, numbers_csv="1,2,3,4,5,6", score=0)]

    generation_id = service._persist_bet_batch(bets)

    assert generation_id == 41
    assert session.added == bets
    assert session.commit_calls == 1
    assert session.rollback_calls == 0
    assert bets[0].generation_id == 41


def test_bet_batch_rolls_back_the_whole_batch_when_commit_fails(monkeypatch):
    session = _RecordingSession(fail_commit=True)
    monkeypatch.setattr(service, "db", SimpleNamespace(session=session))
    bets = [
        GeneratedBet(quantity=6, numbers_csv="1,2,3,4,5,6", score=0),
        GeneratedBet(quantity=6, numbers_csv="7,8,9,10,11,12", score=0),
    ]

    with pytest.raises(RuntimeError, match="commit failed"):
        service._persist_bet_batch(bets)

    assert session.commit_calls == 1
    assert session.rollback_calls == 1
    assert session.added == []
