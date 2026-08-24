"""Papéis administrativos para as contas.

Contas existentes recebem o papel de administrador para preservar seu acesso
à gestão durante a migração. Concursos, apostas e configurações não são
alterados: continuam formando um acervo compartilhado.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260824_0003_user_roles"
down_revision = "20260814_0002_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(length=20), nullable=True))
    op.execute("UPDATE users SET role = 'admin' WHERE role IS NULL")
    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default=sa.text("'operador'"),
    )
    op.create_check_constraint(
        "ck_users_role", "users", "role IN ('admin', 'operador')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
