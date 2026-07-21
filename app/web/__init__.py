"""Blueprint web e registro dos modulos de rota."""

from flask import Blueprint

from ..core.security import register_security_hooks


bp = Blueprint("web", __name__)
register_security_hooks(bp)

# Os imports registram as rotas no blueprint compartilhado.
from . import bets, contests, dashboard, settings  # noqa: E402, F401

__all__ = ("bp",)
