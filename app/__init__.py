from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Mapping
from pathlib import Path

from flask import Flask, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user
from sharedauth.access import requer_login, requer_troca_de_senha
from sharedauth.config import ler_flag, montar_url_postgres
from sharedauth.csrf import iniciar_csrf
from sharedauth.health import registrar_health
from sharedauth.ratelimit import LIMITE_LOGIN_PADRAO, aplicar_limite, iniciar_limiter
from sharedauth.secrets import resolver_segredo
from sharedauth.session import (
    configurar_sessao,
    marca_de_sessao,
    marcas_conferem,
    separar_identificador,
)
from sharedauth.ui import registrar_ui
from sqlalchemy import select
from werkzeug.middleware.proxy_fix import ProxyFix

from .core.formatting import format_brl_without_cents
from .extensions import db, login_manager, migrate
from .web.helpers import flashed_avisos

# Endpoints alcançáveis sem sessão. Mantida deliberadamente curta: a lista é de
# rotas **públicas**, não de rotas protegidas, para que uma rota nova nasça
# protegida em vez de nascer aberta.
#
# `health` é público porque quem consulta é o Docker, de dentro da rede do
# Compose, sem sessão nenhuma. Ele não expõe dado: responde `ok` ou `erro` e
# mais nada — nem versão, nem nome de banco, nem contagem de registros.
#
# `sharedauth_ui.static` serve o CSS e o JS do componente comum de aviso,
# carregados por `base.html` -- e `auth/login.html` estende `base.html`.
# Sem esta entrada os dois arquivos sao pedidos SEM sessao, o gate os
# redireciona para /login, e o navegador recusa o HTML devolvido por
# incompatibilidade de MIME. O efeito visivel e o toast de "Sessao
# encerrada" nunca aparecer depois do logout: quem monta o toast e o JS
# que acabou de ser bloqueado. Nao ha nada sensivel neles -- sao dois
# estaticos da biblioteca.
PUBLIC_ENDPOINTS = frozenset({"web.login", "static", "health", "sharedauth_ui.static"})

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


def _ler_segredo_por_arquivo(nome: str) -> str:
    """Segredo por arquivo, sem transformá-lo em configuração padrão.

    `aceitar_variavel=False`: a forma direta, onde existe, é tratada pelo
    chamador com semântica própria (ver `SECRET_KEY` em `create_app`).
    Ausência devolve string vazia, que é o que os chamadores testam.
    """
    return resolver_segredo(nome, aceitar_variavel=False) or ""


def _database_uri_from_environment() -> str:
    """Obtém URL explícita ou monta a conexão a partir de segredo de arquivo."""
    database_uri = os.environ.get("DATABASE_URL", "").strip()
    if database_uri:
        return database_uri

    host = os.environ.get("DB_HOST", "").strip()
    usuario = os.environ.get("DB_USER", "").strip()
    banco = os.environ.get("DB_NAME", "").strip()
    senha = _ler_segredo_por_arquivo("DB_PASSWORD")
    if not host:
        raise RuntimeError("DB_HOST é obrigatório no ambiente PostgreSQL.")
    if not usuario:
        raise RuntimeError("DB_USER é obrigatório no ambiente PostgreSQL.")
    if not banco:
        raise RuntimeError("DB_NAME é obrigatório no ambiente PostgreSQL.")
    if not senha:
        raise RuntimeError("DB_PASSWORD_FILE é obrigatório no ambiente PostgreSQL.")
    # `montar_url_postgres` valida a porta e escapa usuário, senha e banco --
    # uma senha com `@`, `/` ou `:` apontaria a conexão para outro lugar sem
    # que nada acusasse erro de escape. Ver sharedauth/config.py.
    try:
        return montar_url_postgres(
            usuario=usuario,
            senha=senha,
            host=host,
            banco=banco,
            porta=os.environ.get("DB_PORT", "5432"),
        )
    except ValueError as erro:
        raise RuntimeError(f"Configuração PostgreSQL inválida: {erro}") from erro


def create_app(config: Mapping[str, object] | None = None) -> Flask:
    _configure_logging()

    app = Flask(__name__)
    base_dir = Path(__file__).resolve().parent.parent
    force_https = ler_flag("MEGA_SENA_FORCE_HTTPS")

    app.config.from_mapping(
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
        TRUSTED_HOSTS=_trusted_hosts_from_environment(),
    )
    if config:
        app.config.update(config)

    # MS-02: host público com transporte inseguro não sobe em silêncio.
    # `MEGA_SENA_FORCE_HTTPS` é o único interruptor que liga `Secure` nos
    # cookies; até 02/09/2026 nada impedia uma recriação do VPS que esquecesse
    # `.env.vps` de subir mesmo assim -- o cookie de sessão saía sem `Secure`,
    # sem nada avisar. Hosts de loopback continuam liberados para
    # desenvolvimento local em HTTP.
    if any(
        host not in _DEFAULT_TRUSTED_HOSTS for host in app.config["TRUSTED_HOSTS"]
    ) and not force_https:
        raise RuntimeError(
            "MEGA_SENA_TRUSTED_HOSTS aponta para host público com "
            "MEGA_SENA_FORCE_HTTPS desligado: o cookie de sessão sairia sem "
            "Secure. Defina MEGA_SENA_FORCE_HTTPS=true, ou restrinja "
            "MEGA_SENA_TRUSTED_HOSTS a host de loopback em desenvolvimento local."
        )

    # `login_user(..., remember=True)` em `web/auth.py` é o padrão deste app,
    # não uma caixa que a pessoa marca. Sem `duracao_lembrete_horas`, valeria o
    # padrão do Flask-Login -- 365 dias -- e um cookie copiado continuaria
    # autenticando por um ano. As duas durações são o teto explícito.
    configurar_sessao(
        app,
        nome_cookie=os.environ.get("MEGA_SENA_SESSION_COOKIE_NAME", "mega_sena_session").strip()
        or "mega_sena_session",
        https_obrigatorio=force_https,
        duracao_horas=24,
        duracao_lembrete_horas=24,
    )

    if ler_flag("MEGA_SENA_TRUST_PROXY_HEADERS"):
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
    secret_key = configured_secret or _ler_segredo_por_arquivo("SECRET_KEY")
    # `SECRET_KEY` no ambiente é compatibilidade para execução manual antiga;
    # o Compose concede a chave exclusivamente por arquivo Docker secret. MS-01:
    # esse caminho de compatibilidade ficava silencioso -- agora registra
    # WARNING identificável, para deixar de ser uma segunda fonte de verdade
    # despercebida para a chave que assina as sessões.
    if not secret_key:
        secret_key = os.environ.get("SECRET_KEY", "").strip()
        if secret_key:
            _log.warning(
                "SECRET_KEY veio da variável de ambiente, não de SECRET_KEY_FILE. "
                "É o caminho de compatibilidade para execução manual antiga; o "
                "Compose concede a chave exclusivamente por arquivo Docker secret."
            )
    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY é obrigatória e não foi definida. "
            "Configure SECRET_KEY_FILE com um segredo estável."
        )

    app.config["SECRET_KEY"] = secret_key

    app.jinja_env.filters["brl0"] = format_brl_without_cents
    # Ponte entre `flash()` e o toast do sharedauth -- ver o docstring de
    # `flashed_avisos` e o bloco que a consome em templates/base.html.
    app.jinja_env.globals["flashed_avisos"] = flashed_avisos

    db.init_app(app)
    migrate.init_app(
        app,
        db,
        directory=str(base_dir / "migrations"),
        compare_type=True,
    )
    iniciar_csrf(app)
    login_manager.init_app(app)
    # MS-03: teto global para as 21 rotas que não são o login -- sem ele,
    # nenhuma delas tinha limite algum. O valor é generoso para o uso normal
    # (folga de tela em tela) e serve de rede para qualquer rota futura que
    # esqueça limite dedicado.
    limiter = iniciar_limiter(app, limites_padrao=["300 per hour", "60 per minute"])
    # Confirmação e aviso (modal + toast) comuns aos quatro apps -- ver
    # sharedauth/ui/__init__.py. Serve CSS/JS com ETag/304 e expõe
    # `sharedauth_icone` para os templates.
    registrar_ui(app)

    from .models import User

    @login_manager.user_loader
    def _load_user(identificador: str):
        """Carrega o dono da sessão, conferindo a marca da senha.

        O identificador guardado no cookie é `id:marca` -- ver `User.get_id`.
        A marca não conferir significa que a senha mudou depois que aquele
        cookie foi emitido: a sessão cai, que é o efeito que faltava para
        trocar a senha derrubar quem entrou com a antiga.

        Formato inválido inclui o identificador ANTIGO (só o id). No primeiro
        acesso depois do deploy as sessões abertas caem, uma vez só.
        """
        partes = separar_identificador(identificador)
        if partes is None:
            return None
        usuario_id, marca = partes
        try:
            usuario = db.session.get(User, int(usuario_id))
        except (TypeError, ValueError):
            return None
        if usuario is None or not usuario.is_active_user:
            return None
        atual = marca_de_sessao(usuario.password_hash, chave_secreta=app.secret_key)
        return usuario if marcas_conferem(marca, atual) else None

    from .web import bp

    app.register_blueprint(bp)

    # O limiter só existe depois de `iniciar_limiter(app)` (uma instância por
    # `create_app()`, não um singleton de módulo — ver extensions.py), então a
    # rota de login não pode carregar `@limiter.limit(...)` no import de
    # auth.py; ela é aplicada aqui, depois que a rota já está registrada.
    #
    # `aplicar_limite` faz a religação de `view_functions` que o Flask-Limiter
    # exige e que já foi esquecida aqui uma vez, deixando o login sem limite
    # nenhum. A mecânica agora mora em `sharedauth.ratelimit`, com teste.
    aplicar_limite(app, limiter, "web.login", LIMITE_LOGIN_PADRAO)

    # MS-03: as duas rotas de importação e o relatório combinatório fazem
    # trabalho caro por requisição -- download externo, planilha de até 10 mil
    # linhas, geração combinatória -- e estão abertas a QUALQUER conta
    # autenticada, sem exigir `admin`. `override_defaults=True` porque este
    # limite é mais estreito que o global acima, não um adicional a ele.
    aplicar_limite(
        app,
        limiter,
        ("web.import_upload", "web.import_from_link", "web.rationale"),
        "10 per minute; 100 per hour",
        override_defaults=True,
    )

    # ------------------------------------------------------------------
    # Sonda de saude dedicada: precisa consultar o banco, responder sem sessao
    # e nao seguir o fluxo da raiz, que redireciona para `/login`.
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
    # Senha redefinida por um administrador vale ate o primeiro acesso: com a
    # marca ligada, toda requisicao cai na tela de troca. Verificar so no
    # login deixaria a marca sem efeito -- bastaria digitar outra URL depois
    # do desvio para seguir usando a senha que o administrador conhece.
    #
    # `web.change_password` e isento pela propria biblioteca. Os quatro daqui
    # sao os que faltam: sem `web.logout` a pessoa fica presa dentro do
    # aplicativo, e sem os dois estaticos a tela de troca chega sem CSS.
    # ------------------------------------------------------------------
    requer_troca_de_senha(
        app,
        endpoint_troca="web.change_password",
        endpoints_isentos=frozenset(
            {"web.logout", "static", "health", "sharedauth_ui.static"}
        ),
        esta_autenticado=lambda: current_user.is_authenticated,
        precisa_trocar=lambda: bool(current_user.must_change_password),
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
                    avisos=[
                        {
                            "mensagem": "O arquivo enviado ultrapassa o limite de 10 MB.",
                            "severidade": "error",
                        }
                    ],
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
