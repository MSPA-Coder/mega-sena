from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path
from typing import Mapping

from flask import Flask, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event

db = SQLAlchemy()

_log = logging.getLogger(__name__)


def create_app(config: Mapping[str, object] | None = None) -> Flask:
    _configure_logging()

    app = Flask(__name__)
    base_dir = Path(__file__).resolve().parent.parent
    instance_dir = base_dir / "instance"
    instance_dir.mkdir(exist_ok=True)
    database_path = instance_dir / "mega_sena.db"

    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{database_path.as_posix()}",
        SQLALCHEMY_ENGINE_OPTIONS={"connect_args": {"timeout": 30}},
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
        TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"],
    )
    if config:
        app.config.update(config)

    # ------------------------------------------------------------------
    # Segurança: chave secreta via variável de ambiente
    # ------------------------------------------------------------------
    configured_secret = app.config.get("SECRET_KEY")
    secret_key = str(configured_secret).strip() if configured_secret else os.environ.get("SECRET_KEY", "").strip()
    if not secret_key:
        _log.warning(
            "SECRET_KEY não definida no ambiente. "
            "Usando chave temporária de desenvolvimento gerada na inicialização — "
            "defina SECRET_KEY antes de expor a aplicação na rede."
        )
        secret_key = secrets.token_urlsafe(32)

    app.config["SECRET_KEY"] = secret_key

    app.jinja_env.filters["brl"] = _format_brl
    app.jinja_env.filters["brl0"] = _format_brl_without_cents

    db.init_app(app)

    from .routes import bp
    app.register_blueprint(bp)

    # ------------------------------------------------------------------
    # Cache-busting de assets estáticos: evita que o navegador continue
    # servindo um style.css antigo do cache após alterações de CSS.
    # ------------------------------------------------------------------
    @app.context_processor
    def _inject_asset_version():
        css_path = Path(app.static_folder or "") / "style.css"
        try:
            version = int(css_path.stat().st_mtime)
        except OSError:
            version = 0
        return {"asset_version": version}

    # ------------------------------------------------------------------
    # Tratamento de arquivo muito grande (413)
    # ------------------------------------------------------------------
    @app.errorhandler(413)
    def _request_entity_too_large(error):  # type: ignore[return]
        flash("O arquivo enviado ultrapassa o limite de 10 MB.")
        return redirect(url_for("web.contests")), 413

    with app.app_context():
        from . import models  # noqa: F401
        from .services import ensure_default_config, ensure_draw_parameters_current

        _configure_sqlite_engine(app)
        db.create_all()
        ensure_default_config()
        ensure_draw_parameters_current()

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


def _configure_sqlite_engine(app: Flask) -> None:
    database_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI", ""))
    if not database_uri.startswith("sqlite:"):
        return

    @event.listens_for(db.engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()


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
