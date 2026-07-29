from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path
from typing import Mapping

from flask import Flask, flash, redirect, url_for

from .core.formatting import format_brl, format_brl_without_cents
from .extensions import db, migrate

_log = logging.getLogger(__name__)

_SUPPORTED_DIALECTS = ("postgresql://", "postgresql+psycopg://")


def create_app(config: Mapping[str, object] | None = None) -> Flask:
    _configure_logging()

    app = Flask(__name__)
    base_dir = Path(__file__).resolve().parent.parent

    app.config.from_mapping(
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        SESSION_COOKIE_NAME=os.environ.get(
            "MEGA_SENA_SESSION_COOKIE_NAME", "mega_sena_session"
        ).strip()
        or "mega_sena_session",
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
        TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"],
    )
    if config:
        app.config.update(config)

    # ------------------------------------------------------------------
    # Banco de dados: PostgreSQL é o único backend operacional suportado.
    # SQLite não é usado para simular PostgreSQL; a única leitura legítima de
    # SQLite no projeto é o script explícito de importação de base legada
    # (scripts/migrate_sqlite_to_postgres.py), que acessa o arquivo diretamente
    # e não passa por esta fábrica de aplicação.
    # ------------------------------------------------------------------
    database_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI", "")).strip()
    if not database_uri:
        database_uri = os.environ.get("DATABASE_URL", "").strip()
    if not database_uri:
        raise RuntimeError(
            "DATABASE_URL não definida. Configure uma URL PostgreSQL "
            "(ex.: postgresql+psycopg://usuario:senha@host:5432/banco). "
            "Veja docs/architecture.md e docs/development.md."
        )
    if not database_uri.startswith(_SUPPORTED_DIALECTS):
        raise RuntimeError(
            "DATABASE_URL deve apontar para PostgreSQL "
            f"({' ou '.join(_SUPPORTED_DIALECTS)}); valor recebido não é suportado."
        )
    app.config["SQLALCHEMY_DATABASE_URI"] = database_uri

    # ------------------------------------------------------------------
    # Segurança: chave secreta via variável de ambiente
    # ------------------------------------------------------------------
    configured_secret = app.config.get("SECRET_KEY")
    secret_key = (
        str(configured_secret).strip()
        if configured_secret
        else os.environ.get("SECRET_KEY", "").strip()
    )
    if not secret_key:
        _log.warning(
            "SECRET_KEY não definida no ambiente. "
            "Usando chave temporária de desenvolvimento gerada na inicialização — "
            "defina SECRET_KEY antes de expor a aplicação na rede."
        )
        secret_key = secrets.token_urlsafe(32)

    app.config["SECRET_KEY"] = secret_key

    app.jinja_env.filters["brl"] = format_brl
    app.jinja_env.filters["brl0"] = format_brl_without_cents

    db.init_app(app)
    migrate.init_app(
        app,
        db,
        directory=str(base_dir / "migrations"),
        compare_type=True,
    )

    from .web import bp

    app.register_blueprint(bp)

    # ------------------------------------------------------------------
    # Cache-busting de assets estáticos: evita que o navegador continue
    # servindo um style.css antigo do cache após alterações de CSS.
    # ------------------------------------------------------------------
    @app.context_processor
    def _inject_asset_version():
        static_dir = Path(app.static_folder or "")
        asset_paths = [
            static_dir / name
            for name in ("style.css", "base.js", "bets.js", "dashboard.js")
        ]
        asset_paths.extend(sorted((static_dir / "css").glob("*.css")))
        mtimes = []
        for asset_path in asset_paths:
            try:
                mtimes.append(asset_path.stat().st_mtime)
            except OSError:
                pass
        version = int(max(mtimes, default=0))
        return {"asset_version": version}

    # ------------------------------------------------------------------
    # Tratamento de arquivo muito grande (413)
    # ------------------------------------------------------------------
    @app.errorhandler(413)
    def _request_entity_too_large(error):  # type: ignore[return]
        flash("O arquivo enviado ultrapassa o limite de 10 MB.")
        return redirect(url_for("web.contests")), 413

    from . import models  # noqa: F401  (garante que os modelos sejam registrados)

    # ------------------------------------------------------------------
    # Comando explícito de seed de dados de aplicação (configuração padrão e
    # parâmetros derivados dos concursos). NUNCA roda automaticamente na
    # construção da aplicação: `create_app()` não faz nenhuma consulta ao
    # banco por conta própria, então pode ser importada com segurança mesmo
    # antes do schema existir (ex.: pelo próprio `flask db upgrade`, que
    # precisa carregar a aplicação para descobrir a configuração do banco).
    # Rode `flask seed-defaults` como uma etapa controlada, sempre depois de
    # `flask db upgrade` e antes de iniciar o servidor. Veja
    # docs/architecture.md e o entrypoint do container.
    # ------------------------------------------------------------------
    @app.cli.command("seed-defaults")
    def _seed_defaults_command() -> None:
        """Garante configuração padrão e parâmetros derivados dos concursos."""
        from .draws.statistics import ensure_draw_parameters_current
        from .settings.service import ensure_default_config

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
