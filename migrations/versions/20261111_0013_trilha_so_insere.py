"""A trilha de auditoria aceita inserção; alterar e apagar ficam com o dono.

O papel da aplicação tinha UPDATE e DELETE em `audit_events` (o `db-provision`
concede DML em todas as tabelas a cada subida, então um REVOKE não duraria), e
o modelo se descrevia como imutável. A aplicação nunca altera nem apaga a
trilha: `reset_all_data` remove só concursos e apostas. Mas um defeito, ou
alguém com a sessão da aplicação, podia apagar o próprio rastro.

O gatilho recusa UPDATE e DELETE de quem não é superusuário. Uma exceção:
`actor_user_id` é `SET NULL`, e apagar um usuário precisa anular a referência
nos eventos dele. Essa alteração, e só ela, passa. O papel administrativo (o do
`migrate`, do backup e da suíte) é superusuário e não é afetado: expurgo e
correção da trilha continuam possíveis, por ele.

Idempotente: `CREATE OR REPLACE` na função e `DROP TRIGGER IF EXISTS` antes de
criar o gatilho.
"""

from alembic import op

revision = "20261111_0013_trilha_so_insere"
down_revision = "20261111_0012_users_um_indice"
branch_labels = None
depends_on = None

FUNCAO = """
CREATE OR REPLACE FUNCTION public.audit_events_somente_insercao() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.actor_user_id IS NULL
            AND to_jsonb(NEW) - 'actor_user_id' = to_jsonb(OLD) - 'actor_user_id' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'audit_events aceita apenas insercao (papel %)', current_user
        USING ERRCODE = 'insufficient_privilege';
END;
$$
"""


def upgrade() -> None:
    op.execute(FUNCAO)
    op.execute("DROP TRIGGER IF EXISTS audit_events_somente_insercao ON public.audit_events")
    op.execute(
        """
        CREATE TRIGGER audit_events_somente_insercao
            BEFORE UPDATE OR DELETE ON public.audit_events
            FOR EACH ROW EXECUTE FUNCTION public.audit_events_somente_insercao()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_somente_insercao ON public.audit_events")
    op.execute("DROP FUNCTION IF EXISTS public.audit_events_somente_insercao()")
