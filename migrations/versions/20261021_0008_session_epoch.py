"""Época de sessão: o logout passa a invalidar o cookie emitido.

O cookie de sessão é assinado e sem estado no servidor: ``logout_user`` só o
apagava no navegador, e uma cópia dele continuava valendo até expirar. A época
entra na marca da sessão (ver ``User.get_id``); o logout a incrementa e toda
cópia anterior deixa de conferir.

Coluna nova com padrão no servidor, e a época 0 mantém a marca idêntica à
anterior: as sessões abertas no deploy continuam válidas, e a imagem anterior
simplesmente ignora a coluna, o que mantém a migração compatível com o
rollback de código e imagem do ``deploy.sh`` (que não reverte schema).

O identificador da revisão tem 28 caracteres porque
``alembic_version.version_num`` é ``varchar(32)``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261021_0008_session_epoch"
down_revision = "20261009_0007_regional_format"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("session_epoch", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "session_epoch")
