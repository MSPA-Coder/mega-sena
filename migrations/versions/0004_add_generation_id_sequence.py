"""Garante identificadores de lote únicos para apostas geradas."""

from alembic import op
import sqlalchemy as sa


revision = "0004_generation_id_sequence"
down_revision = "0003_expand_money"
branch_labels = None
depends_on = None

_SEQUENCE_NAME = "generated_bets_generation_id_seq"


def upgrade() -> None:
    op.execute(sa.text(f"CREATE SEQUENCE {_SEQUENCE_NAME}"))
    op.execute(
        sa.text(
            f"ALTER SEQUENCE {_SEQUENCE_NAME} "
            "OWNED BY generated_bets.generation_id"
        )
    )
    op.execute(
        sa.text(
            "SELECT setval("
            f"'{_SEQUENCE_NAME}', "
            "GREATEST(COALESCE((SELECT MAX(generation_id) FROM generated_bets), 0), 1), "
            "COALESCE((SELECT MAX(generation_id) FROM generated_bets), 0) > 0"
            ")"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"DROP SEQUENCE {_SEQUENCE_NAME}"))
