"""Base do schema: o banco de produção em 03/11/2026, numa revisão só.

Substitui as 10 revisões de 03/08 a 28/10/2026, que continuam no git até o
commit 91c9728. O identificador é o da última delas, de propósito: o banco de
produção já está nela, reconhece esta base como aplicada e não precisa de
comando nenhum. As migrações de dados daquela cadeia (papel das contas antigas,
apostas antigas no concurso 3076) não têm efeito num banco vazio e ficaram de
fora.

Prova: um banco montado pela cadeia antiga e outro por esta base deram
`pg_dump --schema-only` e `--data-only` idênticos.

Restaurar um dump com `alembic_version` diferente deste identificador exige
antes o código de 91c9728 (`flask db upgrade` com ele) e só depois o atual.

Revisão nova: identificador com no máximo 32 caracteres, porque
`alembic_version.version_num` é `varchar(32)` e um id mais longo só falha ao
gravar o carimbo, depois do DDL.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261028_0010_bet_confirmation"
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

_PARIDADE_SQL = " + ".join(f"(CASE WHEN n{i} % 2 = 0 THEN 1 ELSE 0 END)" for i in range(1, 7))


def upgrade() -> None:
    op.create_table(
        "config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_config_key", "config", ["key"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active_user", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("role", sa.String(length=20), nullable=False, server_default=sa.text("'operador'")),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("regional_format", sa.String(length=2), nullable=False, server_default="br"),
        sa.Column("session_epoch", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("role IN ('admin', 'operador')", name="ck_users_role"),
        sa.CheckConstraint("regional_format IN ('br', 'us')", name="ck_users_regional_format_valid"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "import_batches",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ignored_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quarantined_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_batches_actor_user_id", "import_batches", ["actor_user_id"])

    op.create_table(
        "import_quarantine",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("import_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("contest", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_quarantine_import_batch_id", "import_quarantine", ["import_batch_id"])
    op.create_index("ix_import_quarantine_contest", "import_quarantine", ["contest"])

    op.create_table(
        "draws",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contest", sa.Integer(), nullable=False),
        sa.Column("draw_date", sa.Date(), nullable=True),
        *(sa.Column(f"n{i}", sa.Integer(), nullable=False) for i in range(1, 7)),
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
        sa.Column("import_batch_id", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("contest > 0", name="ck_draws_contest_positive"),
        sa.CheckConstraint(
            "n1 >= 1 AND n6 <= 60 AND n1 < n2 AND n2 < n3 AND n3 < n4 AND n4 < n5 AND n5 < n6",
            name="ck_draws_numbers_ordered_and_bounded",
        ),
        sa.CheckConstraint("total_sum = n1 + n2 + n3 + n4 + n5 + n6", name="ck_draws_total_sum_matches_numbers"),
        sa.CheckConstraint(f"even_count = ({_PARIDADE_SQL})", name="ck_draws_even_count_matches_numbers"),
        sa.CheckConstraint(f"consecutive_count = {_CONSECUTIVE_COUNT_SQL}",
                           name="ck_draws_consecutive_count_matches_numbers"),
        sa.CheckConstraint("winners_6 >= 0 AND winners_5 >= 0 AND winners_4 >= 0", name="ck_draws_winners_nonnegative"),
        sa.CheckConstraint(
            "prize_cents >= 0 AND accumulated_cents >= 0 AND quina_rateio_cents >= 0 AND quadra_rateio_cents >= 0",
            name="ck_draws_money_nonnegative",
        ),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"], name="fk_draws_import_batch_id",
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_draws_contest", "draws", ["contest"], unique=True)
    op.create_index("ix_draws_import_batch_id", "draws", ["import_batch_id"])

    op.create_table(
        "generated_bets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generation_id", sa.Integer(), nullable=True),
        sa.Column("numbers_csv", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("contest", sa.Integer(), nullable=True),
        sa.CheckConstraint("quantity BETWEEN 6 AND 20", name="ck_generated_bets_quantity_range"),
        sa.CheckConstraint("score >= 0 AND score <= 1", name="ck_generated_bets_score_range"),
        sa.CheckConstraint("generation_id IS NULL OR generation_id > 0", name="ck_generated_bets_generation_id_positive"),
        sa.CheckConstraint("contest IS NULL OR contest > 0", name="ck_generated_bets_contest_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generated_bets_generation_id", "generated_bets", ["generation_id"])
    op.create_index("ix_generated_bets_contest", "generated_bets", ["contest"])
    op.execute(sa.text("CREATE SEQUENCE generated_bets_generation_id_seq"))
    op.execute(sa.text("ALTER SEQUENCE generated_bets_generation_id_seq OWNED BY generated_bets.generation_id"))

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_entity", "audit_events", ["entity"])
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])

    op.create_table(
        "bet_confirmations",
        sa.Column("token", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("generation_id", sa.Integer(), nullable=False),
        sa.Column("saved_count", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    for tabela in ("bet_confirmations", "audit_events", "generated_bets", "draws",
                   "import_quarantine", "import_batches", "users", "config"):
        op.drop_table(tabela)
