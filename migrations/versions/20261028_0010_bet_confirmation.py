"""Registra a intenção de confirmação e o resultado no mesmo commit."""

from alembic import op
import sqlalchemy as sa

revision = "20261028_0010_bet_confirmation"
down_revision = "20261027_0009_bet_contest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bet_confirmations",
        sa.Column("token", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("generation_id", sa.Integer(), nullable=False),
        sa.Column("saved_count", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("bet_confirmations")
