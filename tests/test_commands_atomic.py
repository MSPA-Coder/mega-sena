"""PostgreSQL real: falha do driver de auditoria não deixa sucesso parcial."""

from concurrent.futures import ThreadPoolExecutor, wait
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import event, text

from app.accounts import commands as accounts
from app.audit.contracts import AuditContext
from app.bets import commands as bets
from app.bets.service import prepare_generated_bets, stage_bet_batch
from app.extensions import db
from app.models import AuditEvent, BetConfirmation, Config, GeneratedBet, User
from app.settings import commands as settings

pytestmark = pytest.mark.banco
PASSWORD = "Public-synthetic-password-20261018"
BET = "37,41,43,47,53,59"


@pytest.fixture
def database(app_com_banco):
    with app_com_banco.app_context():
        db.session.execute(
            text("TRUNCATE audit_events, generated_bets, config, users RESTART IDENTITY CASCADE")
        )
        admin = User(username="atomic_admin", role="admin", is_active_user=True)
        operator = User(username="atomic_operator", role="operador", is_active_user=True)
        admin.set_password(PASSWORD)
        operator.set_password(PASSWORD)
        db.session.add_all([admin, operator, GeneratedBet(quantity=6, numbers_csv=BET, score=0)])
        db.session.commit()
        yield app_com_banco, admin, operator
        db.session.rollback()
        db.session.execute(
            text("TRUNCATE audit_events, generated_bets, config, users RESTART IDENTITY CASCADE")
        )
        db.session.commit()


def _snapshot():
    # Ordenação estável; as sequences não são transacionais e não fazem parte
    # da promessa de rollback. O conteúdo anterior, sim.
    return (
        [
            (b.id, b.numbers_csv, b.generation_id)
            for b in GeneratedBet.query.order_by(GeneratedBet.id)
        ],
        [
            (u.id, u.username, u.role, u.is_active_user, u.password_hash, u.must_change_password)
            for u in User.query.order_by(User.id)
        ],
        [(c.key, c.value) for c in Config.query.order_by(Config.key)],
    )


def _audit_failure(_connection, _cursor, _statement, _parameters, context, _many):
    table = getattr(getattr(context.compiled, "statement", None), "table", None)
    if context.isinsert and table is not None and table.name == "audit_events":
        raise RuntimeError("auditoria indisponível (sintético)")


@pytest.mark.parametrize(
    "operation",
    [
        "confirm",
        "delete",
        "settings",
        "reset",
        "create",
        "provision",
        "password_reset",
        "own_password",
        "active",
        "role",
    ],
)
@pytest.mark.parametrize("fail_audit", [False, True])
def test_command_and_success_event_are_one_transaction(database, operation, fail_audit):
    _, admin, operator = database
    audit = AuditContext(admin.id, {"source": "synthetic-test"})
    first_bet = GeneratedBet.query.first().id
    operations = {
        "confirm": lambda: bets.confirm_generated_bets(6, ["1,2,3,4,5,6"], audit=audit),
        "delete": lambda: bets.delete_saved_bet(first_bet, audit=audit),
        "settings": lambda: settings.update_config_values({"generation_amount": "7"}, audit=audit),
        "reset": lambda: settings.reset_all_data(audit=audit),
        "create": lambda: accounts.create_user("new_synthetic", PASSWORD, actor=admin, audit=audit),
        "provision": lambda: accounts.provision_cli_user("cli_synthetic", PASSWORD),
        "password_reset": lambda: accounts.reset_password(operator, actor=admin, audit=audit),
        "own_password": lambda: accounts.change_own_password(
            operator,
            PASSWORD,
            PASSWORD + "-new",
            PASSWORD + "-new",
            audit=AuditContext(operator.id),
        ),
        "active": lambda: accounts.set_active(operator, False, actor=admin, audit=audit),
        "role": lambda: accounts.set_role(operator, "admin", actor=admin, audit=audit),
    }
    before = _snapshot()
    if fail_audit:
        event.listen(db.engine, "before_cursor_execute", _audit_failure)
        try:
            with pytest.raises(RuntimeError, match="auditoria indisponível"):
                operations[operation]()
        finally:
            event.remove(db.engine, "before_cursor_execute", _audit_failure)
        assert _snapshot() == before
        assert AuditEvent.query.count() == 0
    else:
        operations[operation]()
        assert _snapshot() != before
        assert AuditEvent.query.filter_by(success=True).count() == 1
        assert PASSWORD not in str(AuditEvent.query.first().context)


@pytest.mark.parametrize("same", [True, False])
def test_concurrent_confirmation_preserves_batch_and_event_identity(database, same):
    application, admin, _ = database
    actor_id = admin.id
    barrier = Barrier(4)
    token = str(uuid4())

    def confirm(index):
        with application.app_context():
            numbers = "1,2,3,4,5,6" if same else f"{index + 1},41,43,47,53,59"
            barrier.wait(timeout=10)
            return bets.confirm_generated_bets(6, [numbers], audit=AuditContext(actor_id),
                                               token=token if same else str(uuid4()))

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(confirm, range(4)))
    ids = {r.generation_id for r in results}
    assert all(r.saved_count == 1 for r in results)
    assert len(ids) == (1 if same else 4)
    assert sum(not r.replayed for r in results) == len(ids)
    assert GeneratedBet.query.filter(GeneratedBet.generation_id.in_(ids)).count() == len(ids)
    assert AuditEvent.query.filter_by(action="bets.save", success=True).count() == len(ids)


def test_closure_replay_returns_original_batch_without_second_creation(database):
    _, admin, _ = database
    token = str(uuid4())
    first = bets.confirm_closure_bets(range(1, 8), audit=AuditContext(admin.id), token=token)
    replay = bets.confirm_closure_bets(reversed(range(1, 8)), audit=AuditContext(admin.id), token=token)
    assert first.saved_count == replay.saved_count == 7
    assert first.generation_id == replay.generation_id
    assert not first.replayed and replay.replayed
    assert AuditEvent.query.filter_by(action="bets.save", success=True).count() == 1


def test_distinct_intentions_allow_identical_bets_and_reject_token_reuse(database):
    _, admin, _ = database
    token = str(uuid4())
    audit = AuditContext(admin.id)
    first = bets.confirm_generated_bets(6, [BET], audit=audit, contest=10, token=token)
    second = bets.confirm_generated_bets(6, [BET], audit=audit, contest=10, token=str(uuid4()))
    assert first.generation_id != second.generation_id
    with pytest.raises(RuntimeError, match="outra solicitação"):
        bets.confirm_generated_bets(6, [BET], audit=audit, contest=11, token=token)


def test_last_admin_policy_remains_enforced_in_command(database):
    _, admin, _ = database
    with pytest.raises(ValueError, match="único administrador"):
        accounts.set_role(admin, "operador", actor=admin, audit=AuditContext(admin.id))
    assert db.session.get(User, admin.id).role == "admin"
    assert AuditEvent.query.count() == 0


def test_dois_administradores_nao_removem_ambos_os_papeis_em_concorrencia(database):
    application, admin, _ = database
    outro = User(username="outro_admin", role="admin", is_active_user=True)
    outro.set_password(PASSWORD)
    db.session.add(outro)
    db.session.commit()
    ids = (admin.id, outro.id)
    barrier = Barrier(2)

    def remover_papel(actor_id, target_id):
        with application.app_context():
            actor, target = db.session.get(User, actor_id), db.session.get(User, target_id)
            barrier.wait(timeout=10)
            try:
                accounts.set_role(target, "operador", actor=actor, audit=AuditContext(actor_id))
                return "alterado"
            except ValueError:
                return "recusado"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(remover_papel, ids[0], ids[1]),
                   executor.submit(remover_papel, ids[1], ids[0])]
        assert sorted(f.result(timeout=15) for f in futures) == ["alterado", "recusado"]
    db.session.expire_all()
    assert User.query.filter_by(role="admin", is_active_user=True).count() == 1
    assert AuditEvent.query.filter_by(action="users.set_role", success=True).count() == 1


def test_segunda_confirmacao_com_o_mesmo_token_espera_a_primeira_terminar(database):
    """A trava do token faz a segunda confirmação esperar e devolver o replay.

    Sem ela, a segunda grava e confirma antes e a primeira falha ao confirmar (chave primária repetida).
    O teste de disputa por quatro threads só percebe isso quando roda sozinho; este é determinístico.
    """
    application, admin, _ = database
    token = str(uuid4())
    preparada, liberar = Event(), Event()

    def primeira():
        with application.app_context():
            apostas = prepare_generated_bets(6, [BET])
            for aposta in apostas:
                aposta.contest = 10
            stage_bet_batch(apostas, token, admin.id)
            preparada.set()
            assert liberar.wait(timeout=10)
            db.session.commit()

    def segunda():
        with application.app_context():
            return bets.confirm_generated_bets(
                6, [BET], audit=AuditContext(admin.id), contest=10, token=token
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        a = executor.submit(primeira)
        assert preparada.wait(timeout=10)
        b = executor.submit(segunda)
        # Com a trava a segunda continua bloqueada até aqui; sem ela já terminou.
        wait([b], timeout=1.5)
        liberar.set()
        a.result(timeout=10)
        resultado = b.result(timeout=10)
    assert resultado.replayed
    assert BetConfirmation.query.filter_by(token=token).count() == 1
    assert GeneratedBet.query.filter_by(generation_id=resultado.generation_id).count() == 1
