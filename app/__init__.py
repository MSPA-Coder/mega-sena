from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Mapping
from pathlib import Path

from flask import Flask, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user
from sharedauth.access import requer_login
from sharedauth.csrf import iniciar_csrf
from sharedauth.health import registrar_health
from sharedauth.ratelimit import LIMITE_LOGIN_PADRAO, iniciar_limiter
from sharedauth.session import configurar_sessao
from sqlalchemy import select
from werkzeug.middleware.proxy_fix import ProxyFix

from .core.formatting import format_brl_without_cents
from .extensions import db, login_manager, migrate

# Endpoints alcançáveis sem sessão. Mantida deliberadamente curta: a lista é de
# rotas **públicas**, não de rotas protegidas, para que uma rota nova nasça
# protegida em vez de nascer aberta.
#
# `health` é público porque quem consulta é o Docker, de dentro da rede do
# Compose, sem sessão nenhuma. Ele não expõe dado: responde `ok` ou `erro` e
# mais nada — nem versão, nem nome de banco, nem contagem de registros.
PUBLIC_ENDPOINTS = frozenset({"web.login", "static", "health"})

_log = logging.getLogger(__name__)

_SUPPORTED_DIALECTS = ("postgresql://", "postgresql+psycopg://")
_DEFAULT_TRUSTED_HOSTS = ("localhost", "127.0.0.1", "[::1]")


def _trusted_hosts_from_environment() -> list[str]:
    configured = os.environ.get("MEGA_SENA_TRUSTED_HOSTS", "").strip()
    if not configured:
        return list(_DEFAULT_TRUSTED_HOSTS)

    hosts = [host.strip() for host in configured.split(",")]
    if not all(hosts):
        raise RuntimeError("MEGA_SENA_TRUSTED_HOSTS não pode conter hosts vazios.")
    return hosts


def _environment_flag(name: str) -> bool:
    value = os.environ.get(name, "false").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"", "0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} deve ser true ou false.")


def _ler_segredo_por_arquivo(nome_variavel: str) -> str:
    """Lê um segredo de arquivo sem transformá-lo em configuração padrão."""
    caminho = os.environ.get(nome_variavel, "").strip()
    if not caminho:
        return ""
    try:
        valor = Path(caminho).read_text(encoding="utf-8").strip()
    except OSError as erro:
        raise RuntimeError(f"Não foi possível ler o segredo indicado por {nome_variavel}.") from erro
    if not valor:
        raise RuntimeError(f"O arquivo indicado por {nome_variavel} está vazio.")
    return valor


def _database_uri_from_environment() -> str:
    """Obtém URL explícita ou monta a conexão a partir de segredo de arquivo."""
    database_uri = os.environ.get("DATABASE_URL", "").strip()
    if database_uri:
        return database_uri

    host = os.environ.get("DB_HOST", "").strip()
    usuario = os.environ.get("DB_USER", "").strip()
    banco = os.environ.get("DB_NAME", "").strip()
    senha = _ler_segredo_por_arquivo("DB_PASSWORD_FILE")
    if not host:
        raise RuntimeError("DB_HOST é obrigatório no ambiente PostgreSQL.")
    if not usuario:
        raise RuntimeError("DB_USER é obrigatório no ambiente PostgreSQL.")
    if not banco:
        raise RuntimeError("DB_NAME é obrigatório no ambiente PostgreSQL.")
    if not senha:
        raise RuntimeError("DB_PASSWORD_FILE é obrigatório no ambiente PostgreSQL.")
    try:
        porta = int(os.environ.get("DB_PORT", "5432"))
    except ValueError as erro:
        raise RuntimeError("DB_PORT deve ser uma porta PostgreSQL válida.") from erro

    from sqlalchemy.engine import URL

    return URL.create(
        "postgresql+psycopg",
        username=usuario,
        password=senha,
        host=host,
        port=porta,
        database=banco,
    ).render_as_string(hide_password=False)


def create_app(config: Mapping[str, object] | None = None) -> Flask:
    _configure_logging()

    app = Flask(__name__)
    base_dir = Path(__file__).resolve().parent.parent
    force_https = _environment_flag("MEGA_SENA_FORCE_HTTPS")

    app.config.from_mapping(
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        TRUSTED_HOSTS=_trusted_hosts_from_environment(),
    )
    if config:
        app.config.update(config)

    configurar_sessao(
        app,
        nome_cookie=os.environ.get("MEGA_SENA_SESSION_COOKIE_NAME", "mega_sena_session").strip()
        or "mega_sena_session",
        https_obrigatorio=force_https,
    )

    if _environment_flag("MEGA_SENA_TRUST_PROXY_HEADERS"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1)

    # ------------------------------------------------------------------
    # Banco de dados: PostgreSQL é o único backend suportado, na aplicação e
    # nos testes de persistência. Constraints, tipos de coluna e comportamento
    # transacional são um contrato de dialeto — aceitar outro backend aqui
    # daria uma confiança que não existe. A recusa é explícita e vem antes de
    # qualquer conexão.
    # ------------------------------------------------------------------
    database_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI", "")).strip()
    if not database_uri:
        database_uri = _database_uri_from_environment()
    if not database_uri:
        raise RuntimeError(
            "A configuração PostgreSQL não foi definida. Configure DATABASE_URL ou "
            "DB_HOST, DB_USER, DB_NAME e DB_PASSWORD_FILE. "
            "Veja docs/architecture.md e docs/development.md."
        )
    if not database_uri.startswith(_SUPPORTED_DIALECTS):
        raise RuntimeError(
            "DATABASE_URL deve apontar para PostgreSQL "
            f"({' ou '.join(_SUPPORTED_DIALECTS)}); valor recebido não é suportado."
        )
    app.config["SQLALCHEMY_DATABASE_URI"] = database_uri

    # ------------------------------------------------------------------
    # Segurança: chave secreta por arquivo de segredo
    # ------------------------------------------------------------------
    # A chave é exigida do ambiente e a aplicação falha ao subir se faltar.
    # Gerar uma chave efêmera como fallback seria pior que falhar: mascara a
    # ausência da configuração e invalida toda sessão a cada reinício, o que
    # aparece para quem usa como "o sistema me desloga sozinho".
    configured_secret = str(app.config.get("SECRET_KEY") or "").strip()
    secret_key = configured_secret or _ler_segredo_por_arquivo("SECRET_KEY_FILE")
    # `SECRET_KEY` no ambiente é compatibilidade para execução manual antiga;
    # o Compose concede a chave exclusivamente por arquivo Docker secret.
    if not secret_key:
        secret_key = os.environ.get("SECRET_KEY", "").strip()
    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY é obrigatória e não foi definida. "
            "Configure SECRET_KEY_FILE com um segredo estável."
        )

    app.config["SECRET_KEY"] = secret_key

    app.jinja_env.filters["brl0"] = format_brl_without_cents

    db.init_app(app)
    migrate.init_app(
        app,
        db,
        directory=str(base_dir / "migrations"),
        compare_type=True,
    )
    iniciar_csrf(app)
    login_manager.init_app(app)
    limiter = iniciar_limiter(app)

    from .models import User

    @login_manager.user_loader
    def _load_user(user_id: str):
        return db.session.get(User, int(user_id))

    from .web import bp

    app.register_blueprint(bp)

    # O limiter só existe depois de `iniciar_limiter(app)` (uma instância por
    # `create_app()`, não um singleton de módulo — ver extensions.py), então a
    # rota de login não pode carregar `@limiter.limit(...)` no import de
    # auth.py; ela é aplicada aqui, depois que a rota já está registrada.
    # `RouteLimit.__call__` devolve uma função *nova*, embrulhada — descartar
    # o retorno (não reatribuir a `view_functions`) deixaria o limite
    # decorado e nunca aplicado, com toda requisição chamando a view original
    # sem limite nenhum.
    app.view_functions["web.login"] = limiter.limit(LIMITE_LOGIN_PADRAO)(
        app.view_functions["web.login"]
    )

    # ------------------------------------------------------------------
    # Sonda de saúde. Antes desta rota existir, o `healthcheck:` do Compose
    # batia na raiz do site — que sem sessão redireciona para `/login`. O
    # Docker via 200 e declarava o container saudável mesmo com o banco fora,
    # que é exatamente a situação que o health check deveria detectar.
    #
    # `limiter=` isenta a rota do limite global: uma sonda a cada 60s não pode
    # competir com o orçamento de requisições de quem está usando o sistema.
    # ------------------------------------------------------------------
    registrar_health(
        app,
        servico="mega-sena",
        verificar=lambda: db.session.execute(select(1)),
        limiter=limiter,
    )

    # ------------------------------------------------------------------
    # Nega por padrão: toda requisição exige sessão, exceto os endpoints
    # listados em PUBLIC_ENDPOINTS. Ficar do lado de "listar o que é público"
    # é o que garante que uma rota acrescentada amanhã já nasça protegida.
    # ------------------------------------------------------------------
    requer_login(
        app,
        endpoints_publicos=PUBLIC_ENDPOINTS,
        endpoint_login="web.login",
        esta_autenticado=lambda: current_user.is_authenticated,
        prefixo_api=None,
        usar_hx_redirect=True,
    )

    # ------------------------------------------------------------------
    # Cache-busting de assets estáticos: evita que o navegador continue
    # servindo um style.css antigo do cache após alterações de CSS.
    # ------------------------------------------------------------------
    @app.context_processor
    def _inject_asset_version():
        static_dir = Path(app.static_folder or "")
        asset_paths = [
            static_dir / name
            for name in (
                "style.css",
                "base.js",
                "bets.js",
                "vendor/htmx-2.0.10.min.js",
            )
        ]
        asset_paths.extend(sorted((static_dir / "css").glob("*.css")))
        mtimes = []
        for asset_path in asset_paths:
            # Um asset ausente apenas não entra no cálculo da versão.
            with contextlib.suppress(OSError):
                mtimes.append(asset_path.stat().st_mtime)
        version = int(max(mtimes, default=0))
        return {"asset_version": version}

    # ------------------------------------------------------------------
    # Tratamento de arquivo muito grande (413)
    # ------------------------------------------------------------------
    @app.errorhandler(413)
    def _request_entity_too_large(error):  # type: ignore[return]
        if request.headers.get("HX-Request", "").lower() == "true":
            response = make_response(
                render_template(
                    "contests/_import_feedback.html",
                    message="O arquivo enviado ultrapassa o limite de 10 MB.",
                ),
                413,
            )
            response.vary.add("HX-Request")
            return response
        flash("O arquivo enviado ultrapassa o limite de 10 MB.", "error")
        return redirect(url_for("web.contests")), 413

    from . import models  # noqa: F401  (garante que os modelos sejam registrados)
    from .cli import register_commands

    register_commands(app)

    # `create_app()` não faz nenhuma consulta ao banco por conta própria, então
    # pode ser importada com segurança mesmo antes de o schema existir — é o
    # que permite ao próprio `flask db upgrade` carregar a aplicação para
    # descobrir a configuração do banco. Aplicar migrações é uma etapa
    # controlada e separada; veja docs/architecture.md e o entrypoint.
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
