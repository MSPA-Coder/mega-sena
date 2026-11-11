"""Remove a restrição `uq_users_username`, duplicada do índice único.

A migração-base criou `uq_users_username` (UNIQUE) e `ix_users_username`
(índice único) sobre a mesma coluna. O modelo declara só o índice
(`unique=True, index=True`), então `flask db check` já nascia vermelho e o
Postgres mantinha dois índices iguais numa tabela de poucas linhas. Fica o
índice, que é o que o modelo gera.

Idempotente: num banco que já não tem a restrição, não muda nada. O
downgrade a recria só se faltar.
"""

from alembic import op

revision = "20261111_0012_users_um_indice"
down_revision = "20261104_0011_owner_per_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_users_username")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_users_username'
                  AND conrelid = 'users'::regclass
            ) THEN
                ALTER TABLE users ADD CONSTRAINT uq_users_username UNIQUE (username);
            END IF;
        END
        $$
        """
    )
