"""Schema inicial do Mega Sena AI."""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


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
        sa.Column("prize_cents", sa.Integer(), nullable=False),
        sa.Column("accumulated_cents", sa.Integer(), nullable=False),
        sa.Column("quina_rateio_cents", sa.Integer(), nullable=False),
        sa.Column("quadra_rateio_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generated_bets_generation_id", "generated_bets", ["generation_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_generated_bets_generation_id", table_name="generated_bets")
    op.drop_table("generated_bets")
    op.drop_index("ix_draws_contest", table_name="draws")
    op.drop_table("draws")
    op.drop_index("ix_config_key", table_name="config")
    op.drop_table("config")
