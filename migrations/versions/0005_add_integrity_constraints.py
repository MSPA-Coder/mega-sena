"""Protege no PostgreSQL os invariantes duráveis de concursos e apostas."""

from alembic import op
import sqlalchemy as sa


revision = "0005_integrity_constraints"
down_revision = "0004_generation_id_sequence"
branch_labels = None
depends_on = None


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


_CONSTRAINTS = (
    (
        "draws",
        "ck_draws_contest_positive",
        "contest > 0",
    ),
    (
        "draws",
        "ck_draws_numbers_ordered_and_bounded",
        "n1 >= 1 AND n6 <= 60 AND n1 < n2 AND n2 < n3 "
        "AND n3 < n4 AND n4 < n5 AND n5 < n6",
    ),
    (
        "draws",
        "ck_draws_total_sum_matches_numbers",
        "total_sum = n1 + n2 + n3 + n4 + n5 + n6",
    ),
    (
        "draws",
        "ck_draws_even_count_matches_numbers",
        "even_count = "
        "((CASE WHEN n1 % 2 = 0 THEN 1 ELSE 0 END) + "
        "(CASE WHEN n2 % 2 = 0 THEN 1 ELSE 0 END) + "
        "(CASE WHEN n3 % 2 = 0 THEN 1 ELSE 0 END) + "
        "(CASE WHEN n4 % 2 = 0 THEN 1 ELSE 0 END) + "
        "(CASE WHEN n5 % 2 = 0 THEN 1 ELSE 0 END) + "
        "(CASE WHEN n6 % 2 = 0 THEN 1 ELSE 0 END))",
    ),
    (
        "draws",
        "ck_draws_consecutive_count_matches_numbers",
        f"consecutive_count = {_CONSECUTIVE_COUNT_SQL}",
    ),
    (
        "draws",
        "ck_draws_winners_nonnegative",
        "winners_6 >= 0 AND winners_5 >= 0 AND winners_4 >= 0",
    ),
    (
        "draws",
        "ck_draws_money_nonnegative",
        "prize_cents >= 0 AND accumulated_cents >= 0 AND "
        "quina_rateio_cents >= 0 AND quadra_rateio_cents >= 0",
    ),
    (
        "generated_bets",
        "ck_generated_bets_quantity_range",
        "quantity BETWEEN 6 AND 20",
    ),
    (
        "generated_bets",
        "ck_generated_bets_score_range",
        "score >= 0 AND score <= 1",
    ),
    (
        "generated_bets",
        "ck_generated_bets_generation_id_positive",
        "generation_id IS NULL OR generation_id > 0",
    ),
)


def upgrade() -> None:
    # NOT VALID evita reescrever tabelas grandes. A validação logo em seguida
    # mantém a migração segura: se houver uma base legada inconsistente, o
    # upgrade falha sem alterar dados em vez de corrigi-los silenciosamente.
    for table_name, constraint_name, condition in _CONSTRAINTS:
        op.execute(
            sa.text(
                f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} "
                f"CHECK ({condition}) NOT VALID"
            )
        )
        op.execute(
            sa.text(f"ALTER TABLE {table_name} VALIDATE CONSTRAINT {constraint_name}")
        )


def downgrade() -> None:
    for table_name, constraint_name, _condition in reversed(_CONSTRAINTS):
        op.drop_constraint(constraint_name, table_name=table_name, type_="check")
