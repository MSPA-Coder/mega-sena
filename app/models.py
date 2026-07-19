from __future__ import annotations

from datetime import datetime, timezone
from . import db


def _utcnow() -> datetime:
    """Retorna o instante atual em UTC como objeto timezone-aware."""
    return datetime.now(timezone.utc)


class Draw(db.Model):
    __tablename__ = "draws"

    id = db.Column(db.Integer, primary_key=True)
    contest = db.Column(db.Integer, nullable=False, unique=True, index=True)
    draw_date = db.Column(db.Date, nullable=True)
    n1 = db.Column(db.Integer, nullable=False)
    n2 = db.Column(db.Integer, nullable=False)
    n3 = db.Column(db.Integer, nullable=False)
    n4 = db.Column(db.Integer, nullable=False)
    n5 = db.Column(db.Integer, nullable=False)
    n6 = db.Column(db.Integer, nullable=False)
    total_sum = db.Column(db.Integer, nullable=False, default=0)
    even_count = db.Column(db.Integer, nullable=False, default=0)
    consecutive_count = db.Column(db.Integer, nullable=False, default=0)
    winners_6 = db.Column(db.Integer, nullable=False, default=0)
    winners_5 = db.Column(db.Integer, nullable=False, default=0)
    winners_4 = db.Column(db.Integer, nullable=False, default=0)
    prize_cents = db.Column(db.Integer, nullable=False, default=0)
    accumulated_cents = db.Column(db.Integer, nullable=False, default=0)
    quina_rateio_cents = db.Column(db.Integer, nullable=False, default=0)
    quadra_rateio_cents = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    @property
    def numbers(self) -> list[int]:
        return [self.n1, self.n2, self.n3, self.n4, self.n5, self.n6]


class GeneratedBet(db.Model):
    __tablename__ = "generated_bets"

    id = db.Column(db.Integer, primary_key=True)
    generation_id = db.Column(db.Integer, nullable=True, index=True)
    numbers_csv = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=6)
    score = db.Column(db.Float, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    @property
    def numbers(self) -> list[int]:
        return [int(x) for x in self.numbers_csv.split(",") if x]


class Config(db.Model):
    __tablename__ = "config"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), nullable=False, unique=True, index=True)
    value = db.Column(db.String(200), nullable=False, default="")
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)
