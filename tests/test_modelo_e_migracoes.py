"""O esquema que as migrações montam é o que os modelos declaram.

É o `flask db check` dentro da suíte: com o banco já migrado pela fixture
`app_com_banco`, qualquer coluna, índice ou restrição que o modelo tem e a
revisão não cria (ou o contrário) reprova aqui. Sem este teste o desvio só
aparecia quando alguém lembrava de rodar o comando à mão.
"""

import pytest
from flask_migrate import check

pytestmark = pytest.mark.banco


def test_modelos_e_migracoes_nao_divergem(app_com_banco) -> None:
    with app_com_banco.app_context():
        check()
