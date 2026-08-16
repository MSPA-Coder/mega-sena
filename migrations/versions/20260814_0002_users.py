"""Tabela de usuarios.

A aplicacao passou a exigir autenticacao. Nao ha dono de dado: concursos,
apostas e configuracoes seguem sendo um acervo unico, visivel por qualquer
usuario autenticado — esta revisao estabelece quem entra, nao o que cada um ve.

Revision ID: 20260814_0002_users
Revises: 20260803_baseline
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260814_0002_users"
down_revision = "20260803_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "is_active_user",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
