"""Amplia valores monetarios para inteiros de 64 bits no PostgreSQL."""

from alembic import op
import sqlalchemy as sa


revision = "0003_expand_money"
down_revision = "0002_repair_indexes"
branch_labels = None
depends_on = None

_MONEY_COLUMNS = (
    "prize_cents",
    "accumulated_cents",
    "quina_rateio_cents",
    "quadra_rateio_cents",
)


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    if _is_sqlite():
        with op.batch_alter_table("draws") as batch_op:
            for column_name in _MONEY_COLUMNS:
                batch_op.alter_column(
                    column_name,
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False,
                )
        return
    for column_name in _MONEY_COLUMNS:
        op.alter_column(
            "draws",
            column_name,
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=False,
        )


def downgrade() -> None:
    if _is_sqlite():
        with op.batch_alter_table("draws") as batch_op:
            for column_name in _MONEY_COLUMNS:
                batch_op.alter_column(
                    column_name,
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False,
                )
        return
    for column_name in _MONEY_COLUMNS:
        op.alter_column(
            "draws",
            column_name,
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=False,
        )
