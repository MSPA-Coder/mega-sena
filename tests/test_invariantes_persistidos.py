"""Os valores derivados das dezenas, provados no banco.

Fase F1 do LEVANTAMENTO_2026-09.md (achados L01 e L02).

O `AGENTS.md` é explícito: "As `CHECK constraints` de `Draw` protegem valores
derivados das dezenas. Não duplique essa garantia com reparo silencioso em
Python." A instrução é boa e a implementação a respeita -- mas a garantia
inteira mora no PostgreSQL, e a suíte recusava a conexão de propósito. Ou seja,
a proteção existia e nunca havia sido exercitada.

É um caso mais forte do que o de uma constraint comum. `total_sum`,
`even_count` e `consecutive_count` são redundância deliberada: guardam o que
poderia ser recalculado a partir de `n1..n6`. Redundância só é segura enquanto
alguém garante a coerência, e aqui esse alguém é o banco. Se uma dessas
constraints sumisse numa migração, nada em Python notaria -- os cálculos
continuariam certos para linhas novas, e as linhas incoerentes entrariam pela
importação, pelo `psql` ou por um caminho de código novo.

Este arquivo mede só isso, e não tenta cobertura de domínio.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.models import Draw

pytestmark = pytest.mark.banco


# Um concurso real: 6 dezenas ordenadas, com os derivados corretos.
# soma = 4+11+23+35+47+52 = 172; pares = 4, 52 -> 2; consecutivos = nenhum -> 0.
DEZENAS = {"n1": 4, "n2": 11, "n3": 23, "n4": 35, "n5": 47, "n6": 52}


def _sorteio(**campos):
    padrao = {
        "contest": 9999,
        "draw_date": date(2026, 6, 10),
        **DEZENAS,
        "total_sum": 172,
        "even_count": 2,
        "consecutive_count": 0,
    }
    padrao.update(campos)
    return Draw(**padrao)


def test_o_cenario_base_e_aceito(sessao):
    """Controle: se este falhar, os demais não significam nada.

    Um teste que só sabe recusar pode estar recusando tudo. Este prova que a
    linha coerente entra.
    """
    sessao.add(_sorteio())
    sessao.flush()

    assert sessao.query(Draw).count() == 1


# ---------------------------------------------------------------------------
# Os derivados têm de bater com as dezenas
# ---------------------------------------------------------------------------


def test_banco_recusa_soma_que_nao_bate_com_as_dezenas(sessao):
    """`total_sum` é redundante, e a constraint é o que a mantém honesta."""
    sessao.add(_sorteio(total_sum=171))
    with pytest.raises(IntegrityError, match="ck_draws_total_sum_matches_numbers"):
        sessao.flush()


def test_banco_recusa_contagem_de_pares_errada(sessao):
    sessao.add(_sorteio(even_count=3))
    with pytest.raises(IntegrityError, match="ck_draws_even_count_matches_numbers"):
        sessao.flush()


def test_banco_recusa_contagem_de_consecutivos_errada(sessao):
    sessao.add(_sorteio(consecutive_count=1))
    with pytest.raises(IntegrityError, match="ck_draws_consecutive_count_matches_numbers"):
        sessao.flush()


def test_banco_reconhece_consecutivos_de_verdade(sessao):
    """A constraint conta de verdade, e não apenas compara com zero.

    `consecutive_count` é o COMPRIMENTO DA MAIOR SEQUÊNCIA, não a quantidade de
    pares vizinhos -- o `GREATEST(...)` em `_CONSECUTIVE_COUNT_SQL` deixa isso
    explícito. Com 22 e 23 lado a lado, o valor correto é **2**, e não 1; aliás,
    1 é impossível por construção, já que os ramos só produzem 0 ou algo de 2 a
    6. A primeira versão deste teste esperava 1 e foi recusada pelo banco.

    Sem este caso, a constraint passaria por boa mesmo se devolvesse sempre
    zero: os outros testes só a exercitam com sorteios sem sequência.
    """
    # 4, 11, 22, 23, 47, 52 -> soma 159, pares 3 (4, 22, 52), maior sequência 2.
    # Os outros derivados vão CERTOS de propósito: cada caso deste arquivo viola
    # uma constraint só, senão outra dispara antes e o teste passa pelo motivo
    # errado -- foi o que aconteceu na primeira rodada.
    dezenas = {"n1": 4, "n2": 11, "n3": 22, "n4": 23, "n5": 47, "n6": 52}

    sessao.add(_sorteio(**dezenas, total_sum=159, even_count=3, consecutive_count=0))
    with pytest.raises(IntegrityError, match="ck_draws_consecutive_count_matches_numbers"):
        sessao.flush()
    sessao.rollback()

    sessao.add(_sorteio(**dezenas, total_sum=159, even_count=3, consecutive_count=2))
    sessao.flush()  # agora bate


# ---------------------------------------------------------------------------
# As dezenas em si: faixa e ordem
# ---------------------------------------------------------------------------


def test_banco_recusa_dezena_fora_da_faixa(sessao):
    """A Mega-Sena vai de 1 a 60, e o banco sabe disso."""
    # 61 no lugar do 52 muda soma (181) e paridade (só o 4 é par). Os dois
    # derivados vão corrigidos para que a única violação seja a da faixa.
    sessao.add(_sorteio(n6=61, total_sum=181, even_count=1))
    with pytest.raises(IntegrityError, match="ck_draws_numbers_ordered_and_bounded"):
        sessao.flush()


def test_banco_recusa_dezenas_fora_de_ordem(sessao):
    """`n1 < n2 < ... < n6` é o que impede a mesma aposta de ter duas formas.

    Sem a ordenação garantida, o mesmo sorteio poderia ser gravado em ordens
    diferentes e nenhuma comparação por dezenas funcionaria.
    """
    sessao.add(_sorteio(n3=35, n4=23))  # trocados: soma e paridade seguem iguais
    with pytest.raises(IntegrityError, match="ck_draws_numbers_ordered_and_bounded"):
        sessao.flush()


def test_banco_recusa_dezena_repetida(sessao):
    """Repetir uma dezena viola a ordem estrita (`n3 < n4`), e é assim que a
    constraint de ordenação também cobre a duplicidade."""
    sessao.add(_sorteio(n4=23, total_sum=160, even_count=2))
    with pytest.raises(IntegrityError, match="ck_draws_numbers_ordered_and_bounded"):
        sessao.flush()


def test_banco_recusa_concurso_nao_positivo(sessao):
    sessao.add(_sorteio(contest=0))
    with pytest.raises(IntegrityError, match="ck_draws_contest_positive"):
        sessao.flush()


def test_banco_recusa_concurso_duplicado(sessao):
    """`contest` é único: importar o mesmo concurso duas vezes não pode criar
    duas linhas."""
    sessao.add(_sorteio(contest=4242))
    sessao.flush()

    sessao.add(_sorteio(contest=4242))
    with pytest.raises(IntegrityError):
        sessao.flush()


def test_banco_recusa_premio_negativo(sessao):
    sessao.add(_sorteio(prize_cents=-1))
    with pytest.raises(IntegrityError, match="ck_draws_money_nonnegative"):
        sessao.flush()


# ---------------------------------------------------------------------------
# A cadeia de migrações aplicou de verdade
# ---------------------------------------------------------------------------


def test_migracoes_criaram_as_tabelas(sessao):
    """Se qualquer revisão falhasse ao executar, a fixture `app_com_banco` nem
    teria chegado aqui -- o `upgrade()` acontece antes.

    Esta asserção fecha o outro lado: aplicaram *e* produziram o schema
    esperado, não apenas terminaram sem erro.
    """
    tabelas = set(inspect(sessao.get_bind()).get_table_names())

    esperadas = {"draws", "generated_bets", "alembic_version"}
    faltando = esperadas - tabelas
    assert not faltando, f"migrações não criaram: {sorted(faltando)}"


def test_constraints_de_draw_existem_no_banco(sessao):
    """Declarar em `__table_args__` e esquecer de migrar deixa o código
    parecendo protegido e o banco aceitando qualquer coisa."""
    existentes = set(
        sessao.execute(
            text(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'draws'::regclass"
            )
        ).scalars()
    )

    esperadas = {
        "ck_draws_contest_positive",
        "ck_draws_numbers_ordered_and_bounded",
        "ck_draws_total_sum_matches_numbers",
        "ck_draws_even_count_matches_numbers",
        "ck_draws_consecutive_count_matches_numbers",
        "ck_draws_winners_nonnegative",
        "ck_draws_money_nonnegative",
    }
    faltando = esperadas - existentes
    assert not faltando, (
        f"declaradas no modelo mas ausentes no banco: {sorted(faltando)}. "
        "Provavelmente falta gerar ou aplicar uma migração."
    )


def test_o_banco_esta_na_cabeca_da_cadeia(sessao):
    """`test_schema_bootstrap.py` já confere que o grafo tem uma cabeça só,
    lendo os arquivos. Aqui a pergunta é outra: o banco que a suíte acabou de
    construir parou nela."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    versoes = sessao.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    assert len(versoes) == 1, f"esperava uma revisão aplicada, encontrou {versoes}"

    configuracao = Config()
    configuracao.set_main_option("script_location", "migrations")
    cabeca = ScriptDirectory.from_config(configuracao).get_current_head()

    assert versoes[0] == cabeca, (
        f"o banco parou em {versoes[0]}, mas a cabeça da cadeia é {cabeca}"
    )
