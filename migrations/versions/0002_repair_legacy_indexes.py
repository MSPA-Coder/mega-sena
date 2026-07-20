"""Repara indices que db.create_all nao adicionava a bancos existentes."""

from alembic import op
import sqlalchemy as sa


revision = "0002_repair_indexes"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

_EXPECTED_INDEXES = (
    ("config", "ix_config_key", ["key"], True),
    ("draws", "ix_draws_contest", ["contest"], True),
    ("generated_bets", "ix_generated_bets_generation_id", ["generation_id"], False),
)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table_name, index_name, columns, unique in _EXPECTED_INDEXES:
        existing = {index["name"] for index in inspector.get_indexes(table_name)}
        if index_name not in existing:
            op.create_index(index_name, table_name, columns, unique=unique)


def downgrade() -> None:
    # A revisao apenas repara o schema que a baseline ja declara. Remover esses
    # indices deixaria a revisao 0001 inconsistente, portanto o downgrade e no-op.
    pass
