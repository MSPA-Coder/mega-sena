"""Proveniência e quarentena das importações de concursos."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260919_0006_import_provenance"
down_revision = "20260901_0005_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A revisão 0005 criou a PK como BIGINT, mas não criou uma sequência. A
    # importação agora grava o evento de sucesso na mesma transação e precisa
    # de um gerador seguro também para bancos que já receberam a revisão 0005.
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS audit_events_id_seq"))
    op.execute(
        sa.text(
            "SELECT setval('audit_events_id_seq', "
            "COALESCE((SELECT MAX(id) FROM audit_events), 0) + 1, false)"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE audit_events ALTER COLUMN id "
            "SET DEFAULT nextval('audit_events_id_seq')"
        )
    )
    op.create_table(
        "import_batches",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ignored_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quarantined_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_import_batches_actor_user_id", "import_batches", ["actor_user_id"]
    )

    op.create_table(
        "import_quarantine",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("import_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("contest", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_import_quarantine_import_batch_id",
        "import_quarantine",
        ["import_batch_id"],
    )
    op.create_index("ix_import_quarantine_contest", "import_quarantine", ["contest"])

    op.add_column(
        "draws",
        sa.Column("import_batch_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_draws_import_batch_id",
        "draws",
        "import_batches",
        ["import_batch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_draws_import_batch_id", "draws", ["import_batch_id"])


def downgrade() -> None:
    op.drop_index("ix_draws_import_batch_id", table_name="draws")
    op.drop_constraint("fk_draws_import_batch_id", "draws", type_="foreignkey")
    op.drop_column("draws", "import_batch_id")
    op.drop_index("ix_import_quarantine_contest", table_name="import_quarantine")
    op.drop_index("ix_import_quarantine_import_batch_id", table_name="import_quarantine")
    op.drop_table("import_quarantine")
    op.drop_index("ix_import_batches_actor_user_id", table_name="import_batches")
    op.drop_table("import_batches")
    op.execute(sa.text("ALTER TABLE audit_events ALTER COLUMN id DROP DEFAULT"))
    op.execute(sa.text("DROP SEQUENCE audit_events_id_seq"))
