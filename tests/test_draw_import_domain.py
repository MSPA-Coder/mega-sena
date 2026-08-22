from __future__ import annotations

from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from app.draws import importing


class _FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows.values())


class _FakeDraw:
    query = _FakeQuery({})

    def __init__(self, contest, **values):
        self.contest = contest
        self.draw_date = None
        self.winners_6 = 0
        self.winners_5 = 0
        self.winners_4 = 0
        self.prize_cents = 0
        self.accumulated_cents = 0
        self.quina_rateio_cents = 0
        self.quadra_rateio_cents = 0
        for key, value in values.items():
            setattr(self, key, value)


class _TransactionalSession:
    def __init__(self, rows):
        self.rows = rows
        self.before = {contest: deepcopy(vars(draw)) for contest, draw in rows.items()}
        self.commit_calls = 0
        self.rollback_calls = 0

    def add(self, draw):
        self.rows[draw.contest] = draw

    def commit(self):
        self.commit_calls += 1
        self.before = {
            contest: deepcopy(vars(draw)) for contest, draw in self.rows.items()
        }

    def rollback(self):
        self.rollback_calls += 1
        for contest in list(self.rows):
            if contest not in self.before:
                del self.rows[contest]
        for contest, values in self.before.items():
            vars(self.rows[contest]).clear()
            vars(self.rows[contest]).update(deepcopy(values))


@pytest.fixture
def fake_store(monkeypatch):
    rows = {}
    session = _TransactionalSession(rows)
    _FakeDraw.query = _FakeQuery(rows)
    monkeypatch.setattr(importing, "Draw", _FakeDraw)
    monkeypatch.setattr(importing, "db", SimpleNamespace(session=session))
    return rows, session


def _xlsx(headers, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    stream.seek(0)
    return stream


FULL_HEADERS = [
    "Concurso",
    "Data Sorteio",
    "Bola 1",
    "Bola 2",
    "Bola 3",
    "Bola 4",
    "Bola 5",
    "Bola 6",
    "Ganhadores Sena",
    "Prêmio",
]


def test_import_characterizes_new_unchanged_updated_and_missing_optional_fields(
    fake_store,
):
    rows, session = fake_store
    original = [101, "01/08/2026", 1, 2, 3, 4, 5, 6, 2, "R$ 1.234,56"]

    assert importing.import_results_from_xlsx(_xlsx(FULL_HEADERS, [original])) == {
        "imported": 1,
        "updated": 0,
        "ignored": 0,
    }
    assert importing.import_results_from_xlsx(_xlsx(FULL_HEADERS, [original])) == {
        "imported": 0,
        "updated": 0,
        "ignored": 1,
    }

    updated = [101, "02/08/2026", 7, 8, 9, 10, 11, 12, 3, "2.000,00"]
    assert importing.import_results_from_xlsx(_xlsx(FULL_HEADERS, [updated])) == {
        "imported": 0,
        "updated": 1,
        "ignored": 0,
    }
    assert rows[101].prize_cents == 200_000
    assert rows[101].winners_6 == 3

    required_headers = ["Concurso", *(f"Bola {index}" for index in range(1, 7))]
    changed_numbers = [101, 13, 14, 15, 16, 17, 18]
    assert importing.import_results_from_xlsx(
        _xlsx(required_headers, [changed_numbers])
    ) == {"imported": 0, "updated": 1, "ignored": 0}
    assert rows[101].prize_cents == 200_000
    assert rows[101].winners_6 == 3
    assert session.commit_calls == 4
    assert session.rollback_calls == 0


@pytest.mark.parametrize(
    ("invalid_header", "invalid_value", "error"),
    [
        ("Data Sorteio", "não é data", "Data inválida no concurso 202"),
        ("Prêmio", "não é dinheiro", "Valor monetário inválido no concurso 202"),
    ],
)
def test_import_rolls_back_earlier_valid_changes_when_later_metadata_is_invalid(
    fake_store, invalid_header, invalid_value, error
):
    rows, session = fake_store
    existing = _FakeDraw(
        201,
        n1=1,
        n2=2,
        n3=3,
        n4=4,
        n5=5,
        n6=6,
        total_sum=21,
        even_count=3,
        consecutive_count=6,
        prize_cents=99_900,
    )
    rows[201] = existing
    session.before = {201: deepcopy(vars(existing))}
    headers = ["Concurso", *(f"Bola {index}" for index in range(1, 7)), invalid_header]
    workbook_rows = [
        [201, 10, 20, 30, 40, 50, 60, "01/08/2026" if invalid_header.startswith("Data") else "1.00"],
        [202, 11, 21, 31, 41, 51, 60, invalid_value],
    ]

    with pytest.raises(RuntimeError, match=error):
        importing.import_results_from_xlsx(_xlsx(headers, workbook_rows))

    assert rows[201].n1 == 1
    assert rows[201].n6 == 6
    assert rows[201].prize_cents == 99_900
    assert 202 not in rows
    assert session.commit_calls == 0
    assert session.rollback_calls == 1
