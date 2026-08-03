"""Baseline consolidado do schema PostgreSQL validado em 2026-08-03.

Cria apenas bancos novos. Bancos existentes são adotados pelo procedimento
administrativo que valida backup e estrutura antes de usar ``alembic stamp``.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260803_baseline"
down_revision = None
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


def upgrade() -> None:
    op.create_table(
        "config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", sa.String(length=200), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_config_key", "config", ["key"], unique=True)
    op.create_table(
        "draws",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contest", sa.Integer(), nullable=False),
        sa.Column("draw_date", sa.Date(), nullable=True),
        sa.Column("n1", sa.Integer(), nullable=False),
        sa.Column("n2", sa.Integer(), nullable=False),
        sa.Column("n3", sa.Integer(), nullable=False),
        sa.Column("n4", sa.Integer(), nullable=False),
        sa.Column("n5", sa.Integer(), nullable=False),
        sa.Column("n6", sa.Integer(), nullable=False),
        sa.Column("total_sum", sa.Integer(), nullable=False),
        sa.Column("even_count", sa.Integer(), nullable=False),
        sa.Column("consecutive_count", sa.Integer(), nullable=False),
        sa.Column("winners_6", sa.Integer(), nullable=False),
        sa.Column("winners_5", sa.Integer(), nullable=False),
        sa.Column("winners_4", sa.Integer(), nullable=False),
        sa.Column("prize_cents", sa.BigInteger(), nullable=False),
        sa.Column("accumulated_cents", sa.BigInteger(), nullable=False),
        sa.Column("quina_rateio_cents", sa.BigInteger(), nullable=False),
        sa.Column("quadra_rateio_cents", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("contest > 0", name="ck_draws_contest_positive"),
        sa.CheckConstraint("n1 >= 1 AND n6 <= 60 AND n1 < n2 AND n2 < n3 AND n3 < n4 AND n4 < n5 AND n5 < n6", name="ck_draws_numbers_ordered_and_bounded"),
        sa.CheckConstraint("total_sum = n1 + n2 + n3 + n4 + n5 + n6", name="ck_draws_total_sum_matches_numbers"),
        sa.CheckConstraint("even_count = ((CASE WHEN n1 % 2 = 0 THEN 1 ELSE 0 END) + (CASE WHEN n2 % 2 = 0 THEN 1 ELSE 0 END) + (CASE WHEN n3 % 2 = 0 THEN 1 ELSE 0 END) + (CASE WHEN n4 % 2 = 0 THEN 1 ELSE 0 END) + (CASE WHEN n5 % 2 = 0 THEN 1 ELSE 0 END) + (CASE WHEN n6 % 2 = 0 THEN 1 ELSE 0 END))", name="ck_draws_even_count_matches_numbers"),
        sa.CheckConstraint(f"consecutive_count = {_CONSECUTIVE_COUNT_SQL}", name="ck_draws_consecutive_count_matches_numbers"),
        sa.CheckConstraint("winners_6 >= 0 AND winners_5 >= 0 AND winners_4 >= 0", name="ck_draws_winners_nonnegative"),
        sa.CheckConstraint("prize_cents >= 0 AND accumulated_cents >= 0 AND quina_rateio_cents >= 0 AND quadra_rateio_cents >= 0", name="ck_draws_money_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_draws_contest", "draws", ["contest"], unique=True)
    op.create_table(
        "generated_bets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generation_id", sa.Integer(), nullable=True),
        sa.Column("numbers_csv", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("quantity BETWEEN 6 AND 20", name="ck_generated_bets_quantity_range"),
        sa.CheckConstraint("score >= 0 AND score <= 1", name="ck_generated_bets_score_range"),
        sa.CheckConstraint("generation_id IS NULL OR generation_id > 0", name="ck_generated_bets_generation_id_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generated_bets_generation_id", "generated_bets", ["generation_id"], unique=False)
    op.execute(sa.text("CREATE SEQUENCE generated_bets_generation_id_seq"))
    op.execute(sa.text("ALTER SEQUENCE generated_bets_generation_id_seq OWNED BY generated_bets.generation_id"))


def downgrade() -> None:
    op.execute(sa.text("DROP SEQUENCE generated_bets_generation_id_seq"))
    op.drop_index("ix_generated_bets_generation_id", table_name="generated_bets")
    op.drop_table("generated_bets")
    op.drop_index("ix_draws_contest", table_name="draws")
    op.drop_table("draws")
    op.drop_index("ix_config_key", table_name="config")
    op.drop_table("config")
