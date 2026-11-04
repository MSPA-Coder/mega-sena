"""Apostas, parâmetros de geração e tema passam a ser de cada usuário.

Decisão do mantenedor em 04/11/2026 (ADR 0004, que substitui em parte o ADR
0002): cada conta vê só as próprias apostas, gera com os próprios parâmetros e
leva o próprio tema. O uso hoje é individual; a segunda conta, quando vier, já
nasce isolada.

- `generated_bets.owner_id`: as apostas que já existem vão para a conta `admin`
  de menor id, que em produção é a única com atividade. Com apostas gravadas e
  nenhuma conta `admin`, a migração para sem mexer em nada: não há a quem
  entregá-las. `RESTRICT` porque conta não se apaga (só se desativa), e apagar
  a aposta junto com a conta seria perda silenciosa.
- `user_config`: os padrões de geração de cada pessoa. Sem linha própria, vale
  o padrão do sistema (`config`, depois o do código), que é como cada pessoa
  "começa com uma cópia dos valores atuais" sem semear nada.
- `users.theme`: nulo enquanto a pessoa não escolher; aí vale o cookie do
  navegador, como antes.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261104_0011_owner_per_user"
down_revision = "20261028_0010_bet_confirmation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generated_bets", sa.Column("owner_id", sa.Integer(), nullable=True))
    conexao = op.get_bind()
    if conexao.execute(sa.text("SELECT EXISTS (SELECT 1 FROM generated_bets)")).scalar_one():
        dono = conexao.execute(
            sa.text("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")
        ).scalar()
        if dono is None:
            raise RuntimeError(
                "Há apostas gravadas e nenhuma conta admin para recebê-las: "
                "crie uma conta admin antes de aplicar esta migração."
            )
        conexao.execute(sa.text("UPDATE generated_bets SET owner_id = :dono"), {"dono": dono})
    op.alter_column("generated_bets", "owner_id", nullable=False)
    op.create_foreign_key(
        "fk_generated_bets_owner_id", "generated_bets", "users", ["owner_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_generated_bets_owner_generation", "generated_bets", ["owner_id", "generation_id"]
    )

    op.create_table(
        "user_config",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", sa.String(length=200), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_config_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "key", name="pk_user_config"),
    )

    op.add_column("users", sa.Column("theme", sa.String(length=5), nullable=True))
    op.create_check_constraint(
        "ck_users_theme_valid", "users", "theme IS NULL OR theme IN ('light', 'dark')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_theme_valid", "users", type_="check")
    op.drop_column("users", "theme")
    op.drop_table("user_config")
    op.drop_index("ix_generated_bets_owner_generation", table_name="generated_bets")
    op.drop_constraint("fk_generated_bets_owner_id", "generated_bets", type_="foreignkey")
    op.drop_column("generated_bets", "owner_id")
