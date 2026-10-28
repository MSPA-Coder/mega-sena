"""Associar apostas ao concurso; o acervo anterior pertence ao concurso 3076."""
from alembic import op
import sqlalchemy as sa

revision = "20261027_0009_bet_contest"
down_revision = "20261021_0008_session_epoch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generated_bets", sa.Column("contest", sa.Integer(), nullable=True))
    op.execute("UPDATE generated_bets SET contest = 3076 WHERE contest IS NULL")
    op.create_check_constraint("ck_generated_bets_contest_positive", "generated_bets", "contest IS NULL OR contest > 0")
    op.create_index("ix_generated_bets_contest", "generated_bets", ["contest"])


def downgrade() -> None:
    op.drop_index("ix_generated_bets_contest", table_name="generated_bets")
    op.drop_constraint("ck_generated_bets_contest_positive", "generated_bets", type_="check")
    op.drop_column("generated_bets", "contest")
