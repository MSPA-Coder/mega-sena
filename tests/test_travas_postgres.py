"""Travas de banco: cada teste segura o estado em outra transação.

Padrão: a "primeira operação" muda o estado e fica aberta (sem confirmar). A operação testada precisa
esperar por ela e então enxergar o estado confirmado. Sem a trava, a operação testada decide com o
estado antigo (ou tenta gravar o mesmo registro) e o resultado é errado. Não depende de sorte de
tempo: a primeira operação só libera quando a segunda já esperou ou terminou.
"""

from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date
from io import BytesIO
from threading import Event

import pytest
from openpyxl import Workbook
from sqlalchemy import text, update

from app.bets.service import stage_delete_bet
from app.core.numbers import draw_parameters
from app.draws.importing import IMPORT_ADVISORY_LOCK_KEY, import_results_from_xlsx
from app.extensions import db
from app.models import Config, Draw, GeneratedBet
from app.settings.service import update_config_values

pytestmark = pytest.mark.banco

CONCURSO = 54321
APOSTA = "37,41,43,47,53,59"


def _planilha() -> BytesIO:
    pasta = Workbook()
    folha = pasta.active
    folha.append(["Concurso", "Data Sorteio", "Bola 1", "Bola 2", "Bola 3", "Bola 4", "Bola 5", "Bola 6"])
    folha.append([CONCURSO, "01/08/2026", 1, 2, 3, 4, 5, 6])
    fluxo = BytesIO()
    pasta.save(fluxo)
    pasta.close()
    fluxo.seek(0)
    return fluxo


@pytest.fixture
def aplicacao(app_com_banco):
    def limpar():
        with app_com_banco.app_context():
            db.session.rollback()
            db.session.execute(text("TRUNCATE draws, config, generated_bets RESTART IDENTITY CASCADE"))
            db.session.commit()

    limpar()
    yield app_com_banco
    limpar()


def _com_primeira_operacao_aberta(aplicacao, testada, mexer_no_estado):
    """Roda `testada` enquanto `mexer_no_estado()` segura o estado; devolve (resultado, erro) da testada."""
    preparada, liberar = Event(), Event()

    def primeira():
        with aplicacao.app_context():
            try:
                mexer_no_estado()
                preparada.set()
                assert liberar.wait(timeout=10)
                db.session.commit()
            finally:
                db.session.remove()

    def segunda():
        with aplicacao.app_context():
            try:
                resultado = testada()
                db.session.commit()
                return resultado, None
            except Exception as erro:  # noqa: BLE001 - o teste confere o tipo
                db.session.rollback()
                return None, erro
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(primeira)
        assert preparada.wait(timeout=10)
        b = pool.submit(segunda)
        # Com a trava a segunda continua esperando; sem ela já terminou.
        wait([b], timeout=1.5)
        liberar.set()
        a.result(timeout=10)
        return b.result(timeout=20)


def _importar():
    return import_results_from_xlsx(_planilha())


def test_importacao_espera_a_outra_importacao_e_nao_repete_o_concurso(aplicacao):
    def outra_importacao_em_andamento():
        db.session.execute(text(f"SELECT pg_advisory_xact_lock({IMPORT_ADVISORY_LOCK_KEY})"))
        _inserir_o_concurso()

    resultado, erro = _com_primeira_operacao_aberta(aplicacao, _importar, outra_importacao_em_andamento)

    assert erro is None
    assert resultado == {"imported": 0, "updated": 0, "ignored": 1}
    with aplicacao.app_context():
        assert Draw.query.filter_by(contest=CONCURSO).count() == 1


def _inserir_o_concurso():
    numeros = [1, 2, 3, 4, 5, 6]
    derivados = draw_parameters(numeros)
    db.session.add(
        Draw(
            contest=CONCURSO,
            draw_date=date(2026, 8, 1),
            **{f"n{i}": n for i, n in enumerate(numeros, start=1)},
            total_sum=derivados["total_sum"],
            even_count=derivados["even_count"],
            consecutive_count=derivados["consecutive_count"],
        )
    )
    db.session.flush()


def test_importacao_espera_a_linha_do_concurso_e_decide_sobre_o_estado_novo(aplicacao):
    with aplicacao.app_context():
        assert _importar() == {"imported": 1, "updated": 0, "ignored": 0}

    def outra_transacao_muda_a_data():
        db.session.execute(update(Draw).where(Draw.contest == CONCURSO).values(draw_date=date(2026, 7, 1)))

    resultado, erro = _com_primeira_operacao_aberta(aplicacao, _importar, outra_transacao_muda_a_data)

    assert erro is None
    assert resultado == {"imported": 0, "updated": 1, "ignored": 0}
    with aplicacao.app_context():
        assert Draw.query.filter_by(contest=CONCURSO).one().draw_date == date(2026, 8, 1)


def test_primeiro_salvamento_de_configuracao_espera_o_outro_e_atualiza_em_vez_de_inserir(aplicacao):
    resultado, erro = _com_primeira_operacao_aberta(
        aplicacao,
        lambda: update_config_values({"bet_quantity": "8"}),
        lambda: update_config_values({"bet_quantity": "7"}, commit=False),
    )

    assert erro is None
    assert resultado["bet_quantity"] == "8"
    with aplicacao.app_context():
        assert Config.query.filter_by(key="bet_quantity").one().value == "8"


def test_salvamento_de_configuracao_espera_a_gravacao_em_andamento_das_linhas_existentes(aplicacao):
    with aplicacao.app_context():
        update_config_values({"bet_quantity": "6"})

    def outra_transacao_grava_a_linha():
        db.session.execute(update(Config).where(Config.key == "generation_amount").values(value="9"))

    _, erro = _com_primeira_operacao_aberta(
        aplicacao, lambda: update_config_values({"bet_quantity": "8", "generation_amount": "4"}), outra_transacao_grava_a_linha
    )

    assert erro is None
    with aplicacao.app_context():
        assert Config.query.filter_by(key="generation_amount").one().value == "4"
        assert Config.query.filter_by(key="bet_quantity").one().value == "8"


def test_excluir_aposta_ja_excluida_por_outra_transacao_e_recusado(aplicacao):
    with aplicacao.app_context():
        aposta = GeneratedBet(quantity=6, numbers_csv=APOSTA, score=0)
        db.session.add(aposta)
        db.session.commit()
        aposta_id = aposta.id

    def outra_transacao_exclui():
        db.session.delete(db.session.get(GeneratedBet, aposta_id))
        db.session.flush()

    _, erro = _com_primeira_operacao_aberta(aplicacao, lambda: stage_delete_bet(aposta_id), outra_transacao_exclui)

    assert isinstance(erro, RuntimeError)
    with aplicacao.app_context():
        assert GeneratedBet.query.count() == 0
