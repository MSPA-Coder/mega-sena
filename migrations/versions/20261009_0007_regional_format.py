"""Formato regional (Brasil/EUA) de datas e números, escolhido por usuário.

Só apresentação: nada do que já está gravado muda. Toda conta existente fica em
``br``, o formato que o sistema sempre mostrou.

Coluna nova, com padrão no servidor: a imagem anterior simplesmente a ignora, o
que mantém a migração compatível com o rollback de código e imagem do
``deploy.sh`` (que não reverte schema).

O identificador da revisão tem 29 caracteres porque
``alembic_version.version_num`` é ``varchar(32)``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261009_0007_regional_format"
down_revision = "20260919_0006_import_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("regional_format", sa.String(length=2), nullable=False, server_default="br"),
    )
    op.create_check_constraint(
        "ck_users_regional_format_valid",
        "users",
        "regional_format IN ('br', 'us')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_regional_format_valid", "users", type_="check")
    op.drop_column("users", "regional_format")
