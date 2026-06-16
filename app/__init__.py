from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

_log = logging.getLogger(__name__)


def create_app() -> Flask:
    _configure_logging()

    app = Flask(__name__)
    base_dir = Path(__file__).resolve().parent.parent
    instance_dir = base_dir / "instance"
    instance_dir.mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # Segurança: chave secreta via variável de ambiente
    # ------------------------------------------------------------------
    secret_key = os.environ.get("SECRET_KEY", "").strip()
    if not secret_key:
        _log.warning(
            "SECRET_KEY não definida no ambiente. "
            "Usando chave temporária de desenvolvimento — "
            "defina SECRET_KEY antes de expor a aplicação na rede."
        )
        secret_key = "dev-mega-sena-change-me"

    app.config["SECRET_KEY"] = secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{instance_dir / 'mega_sena.db'}"
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"timeout": 30}}
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Limite de upload: 10 MB (planilhas históricas da Caixa ficam abaixo de 2 MB)
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
    # Proteção básica contra CSRF via cookie SameSite
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_HTTPONLY"] = True

    app.jinja_env.filters["brl"] = _format_brl
    app.jinja_env.filters["brl0"] = _format_brl_without_cents

    db.init_app(app)

    from .routes import bp
    app.register_blueprint(bp)

    # ------------------------------------------------------------------
    # Tratamento de arquivo muito grande (413)
    # ------------------------------------------------------------------
    @app.errorhandler(413)
    def _request_entity_too_large(error):  # type: ignore[return]
        flash("O arquivo enviado ultrapassa o limite de 10 MB.")
        return redirect(url_for("web.import_results")), 413

    with app.app_context():
        from . import models  # noqa: F401
        from .services import ensure_default_config, refresh_draw_parameters

        db.create_all()
        ensure_default_config()
        refresh_draw_parameters()

    return app


def _configure_logging() -> None:
    """Configura logging apenas se ainda não foi configurado externamente."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def _format_brl(cents: int | None) -> str:
    if not cents:
        return ""
    value = cents / 100
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def _format_brl_without_cents(cents: int | None) -> str:
    if not cents:
        return ""
    value = round(cents / 100)
    formatted = f"{value:,}".replace(",", ".")
    return f"R$ {formatted}"
