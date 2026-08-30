"""Autorizacao por papel.

A autenticacao ja e garantida pelo gate de `sharedauth.access.requer_login`
registrado em `create_app`: quando um decorator daqui roda, ha sessao. O que se
decide aqui e o que aquele usuario pode fazer.

Esconder o item no menu e apresentacao, nao controle: um botao ausente nao
impede ninguem de chamar a rota diretamente.

O decorator mora num modulo proprio, e nao junto das rotas de usuario, porque
passou a ter dois consumidores -- Usuarios e Configuracoes. Mesmo desenho do
`app/authorization.py` do ControleRendaVariavel, que resolveu isto antes.
"""

from __future__ import annotations

from collections.abc import Callable

from flask_login import current_user
from sharedauth.access import requer_papel

#: Nome do papel exigido, gravado na view protegida.
#:
#: Existe para que a varredura da URLconf consiga distinguir "protegida por
#: papel" de "embrulhada por qualquer decorator". `functools.wraps` deixa
#: `__wrapped__` em toda view decorada -- inclusive nas que so tem
#: `@login_required` --, entao procurar por `__wrapped__` responde a pergunta
#: errada. Ver `tests/test_autorizacao_por_papel.py`.
PAPEL_ADMIN = "admin"


def _exigir_admin() -> bool:
    """`is_authenticated` na condicao de proposito, embora `requer_login` ja
    garanta sessao em toda rota nao publica: `current_user` e anonimo quando
    nao ha sessao, e `is_admin` nao existe no anonimo do Flask-Login. Sem a
    primeira metade, um erro futuro na lista de endpoints publicos viraria
    AttributeError (500) em vez de 403."""
    return bool(current_user.is_authenticated and current_user.is_admin)


# `prefixo_api=None` porque este app nao serve rotas `/api/` -- ver o mesmo
# argumento em `create_app`.
_recusar_quem_nao_e_admin = requer_papel(
    _exigir_admin,
    prefixo_api=None,
    mensagem="Apenas administradores podem usar esta função.",
)


def admin_required[F: Callable[..., object]](view: F) -> F:
    """Restringe a rota a administradores, marcando a view com o papel.

    A mecanica de recusa vem de `sharedauth.access.requer_papel`, compartilhada
    com o ControleRendaVariavel: 403, nunca redirecionamento para o login --
    quem chegou aqui esta autenticado, e mandar para o login sugeriria que
    entrar de novo resolveria. Quem decide o que e ser admin continua sendo
    este projeto.
    """
    protegida = _recusar_quem_nao_e_admin(view)
    protegida.papel_exigido = PAPEL_ADMIN  # type: ignore[attr-defined]
    return protegida  # type: ignore[return-value]
