"""Marca de troca de senha pendente nas contas.

Contas existentes nascem com a marca desligada. Ligá-la para todo mundo
obrigaria as pessoas que já usam o sistema a trocar a senha ao mesmo tempo,
sem aviso — e não há por que fazer isso: a senha delas não é conhecida por
terceiros. A marca passa a ser ligada apenas pela criação de conta e pela
redefinição feita por um administrador.

Coluna nova, com padrão no servidor: a imagem anterior simplesmente a ignora,
o que mantém a migração compatível com o rollback de código e imagem do
`deploy.sh` (que não reverte schema).

O identificador da revisão tem 28 caracteres porque
`alembic_version.version_num` é `varchar(32)`: um id mais longo passa pela
geração e pelos testes e só falha ao gravar o carimbo, DEPOIS de aplicar o
DDL. Aqui o PostgreSQL desfez tudo junto, mas contar com isso não é plano.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260830_0004_change_password"
down_revision = "20260824_0003_user_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
