"""Extensoes Flask compartilhadas pela aplicacao.

CSRF e rate-limit não moram mais aqui: `sharedauth.csrf.iniciar_csrf` e
`sharedauth.ratelimit.iniciar_limiter` criam uma instância própria por
chamada de `create_app()`, não um singleton de módulo — um singleton
compartilhado entre apps no mesmo processo (como os testes fazem) vazava
isenção de CSRF e zerava contadores de rate-limit entre eles.
"""

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()

login_manager = LoginManager()
login_manager.login_view = "web.login"
login_manager.login_message = "Faça login para continuar."
login_manager.login_message_category = "error"
