from __future__ import annotations

from datetime import UTC, datetime

from flask_login import UserMixin
from sharedauth.passwords import conferir_hash, gerar_hash
from sqlalchemy import CheckConstraint

from .extensions import db

_CONSECUTIVE_COUNT_SQL = (
    "GREATEST("
    "CASE WHEN n2 = n1 + 1 THEN CASE WHEN n3 = n2 + 1 THEN "
    "CASE WHEN n4 = n3 + 1 THEN CASE WHEN n5 = n4 + 1 THEN "
    "CASE WHEN n6 = n5 + 1 THEN 6 ELSE 5 END ELSE 4 END ELSE 3 END "
    "ELSE 2 END ELSE 0 END, "
    "CASE WHEN n3 = n2 + 1 THEN CASE WHEN n4 = n3 + 1 THEN "
    "CASE WHEN n5 = n4 + 1 THEN CASE WHEN n6 = n5 + 1 THEN 5 ELSE 4 END "
    "ELSE 3 END ELSE 2 END ELSE 0 END, "
    "CASE WHEN n4 = n3 + 1 THEN CASE WHEN n5 = n4 + 1 THEN "
    "CASE WHEN n6 = n5 + 1 THEN 4 ELSE 3 END ELSE 2 END ELSE 0 END, "
    "CASE WHEN n5 = n4 + 1 THEN CASE WHEN n6 = n5 + 1 THEN 3 ELSE 2 END "
    "ELSE 0 END, CASE WHEN n6 = n5 + 1 THEN 2 ELSE 0 END)"
)


def _utcnow() -> datetime:
    """Retorna o instante atual em UTC como objeto timezone-aware."""
    return datetime.now(UTC)


class Draw(db.Model):
    __tablename__ = "draws"
    __table_args__ = (
        CheckConstraint("contest > 0", name="ck_draws_contest_positive"),
        CheckConstraint(
            "n1 >= 1 AND n6 <= 60 AND n1 < n2 AND n2 < n3 "
            "AND n3 < n4 AND n4 < n5 AND n5 < n6",
            name="ck_draws_numbers_ordered_and_bounded",
        ),
        CheckConstraint(
            "total_sum = n1 + n2 + n3 + n4 + n5 + n6",
            name="ck_draws_total_sum_matches_numbers",
        ),
        CheckConstraint(
            "even_count = "
            "((CASE WHEN n1 % 2 = 0 THEN 1 ELSE 0 END) + "
            "(CASE WHEN n2 % 2 = 0 THEN 1 ELSE 0 END) + "
            "(CASE WHEN n3 % 2 = 0 THEN 1 ELSE 0 END) + "
            "(CASE WHEN n4 % 2 = 0 THEN 1 ELSE 0 END) + "
            "(CASE WHEN n5 % 2 = 0 THEN 1 ELSE 0 END) + "
            "(CASE WHEN n6 % 2 = 0 THEN 1 ELSE 0 END))",
            name="ck_draws_even_count_matches_numbers",
        ),
        CheckConstraint(
            f"consecutive_count = {_CONSECUTIVE_COUNT_SQL}",
            name="ck_draws_consecutive_count_matches_numbers",
        ),
        CheckConstraint(
            "winners_6 >= 0 AND winners_5 >= 0 AND winners_4 >= 0",
            name="ck_draws_winners_nonnegative",
        ),
        CheckConstraint(
            "prize_cents >= 0 AND accumulated_cents >= 0 AND "
            "quina_rateio_cents >= 0 AND quadra_rateio_cents >= 0",
            name="ck_draws_money_nonnegative",
        ),
    )

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
    prize_cents = db.Column(db.BigInteger, nullable=False, default=0)
    accumulated_cents = db.Column(db.BigInteger, nullable=False, default=0)
    quina_rateio_cents = db.Column(db.BigInteger, nullable=False, default=0)
    quadra_rateio_cents = db.Column(db.BigInteger, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    @property
    def numbers(self) -> list[int]:
        return [self.n1, self.n2, self.n3, self.n4, self.n5, self.n6]


class GeneratedBet(db.Model):
    __tablename__ = "generated_bets"
    __table_args__ = (
        CheckConstraint(
            "quantity BETWEEN 6 AND 20", name="ck_generated_bets_quantity_range"
        ),
        CheckConstraint(
            "score >= 0 AND score <= 1", name="ck_generated_bets_score_range"
        ),
        CheckConstraint(
            "generation_id IS NULL OR generation_id > 0",
            name="ck_generated_bets_generation_id_positive",
        ),
    )

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


ROLE_ADMIN = "admin"
ROLE_OPERADOR = "operador"
USER_ROLES = (ROLE_ADMIN, ROLE_OPERADOR)


class User(UserMixin, db.Model):
    """Usuário da aplicação.

    Autenticar não é o mesmo que particionar dados: concursos, apostas e
    configurações continuam sendo um acervo único, visível por qualquer usuário
    autenticado. Este modelo estabelece *quem entra*, não *o que cada um vê* —
    a segunda coisa exigiria uma decisão de produto sobre o que é privado por
    usuário, registrada em AGENTS.md como lacuna conhecida.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active_user = db.Column(db.Boolean, nullable=False, default=True)
    role = db.Column(db.String(20), nullable=False, default=ROLE_OPERADOR)
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = gerar_hash(password)

    def check_password(self, password: str) -> bool:
        return conferir_hash(self.password_hash, password)

    @property
    def is_active(self) -> bool:
        # `Flask-Login` consulta esta propriedade; a coluna tem outro nome para
        # não colidir com ela.
        return self.is_active_user

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN
