"""PostgreSQL real: falha do driver de auditoria não deixa sucesso parcial."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import event, text

from app.accounts import commands as accounts
from app.audit.contracts import AuditContext
from app.bets import commands as bets
from app.extensions import db
from app.models import AuditEvent, Config, GeneratedBet, User
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

    def confirm(index):
        with application.app_context():
            numbers = "1,2,3,4,5,6" if same else f"{index + 1},41,43,47,53,59"
            barrier.wait(timeout=10)
            return bets.confirm_generated_bets(6, [numbers], audit=AuditContext(actor_id))

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
    first = bets.confirm_closure_bets(range(1, 8), audit=AuditContext(admin.id))
    replay = bets.confirm_closure_bets(reversed(range(1, 8)), audit=AuditContext(admin.id))
    assert first.saved_count == replay.saved_count == 7
    assert first.generation_id == replay.generation_id
    assert not first.replayed and replay.replayed
    assert AuditEvent.query.filter_by(action="bets.save", success=True).count() == 1


def test_last_admin_policy_remains_enforced_in_command(database):
    _, admin, _ = database
    with pytest.raises(ValueError, match="único administrador"):
        accounts.set_role(admin, "operador", actor=admin, audit=AuditContext(admin.id))
    assert db.session.get(User, admin.id).role == "admin"
    assert AuditEvent.query.count() == 0
