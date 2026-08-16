"""Login e logout.

A aplicação nega por padrão: `app/__init__.py` exige sessão em toda requisição
e mantém uma lista curta e explícita de endpoints públicos. Uma lista de rotas
protegidas envelheceria mal, porque a rota nova nasceria desprotegida; a lista
de rotas públicas envelhece bem, porque a rota nova nasce protegida.
"""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db, limiter
from ..models import User
from . import bp


def _safe_next_url() -> str | None:
    """Devolve o destino pós-login apenas quando ele é interno.

    Sem esta checagem, `?next=https://outro.site` transformaria a tela de login
    em um redirecionador aberto.
    """
    next_url = request.args.get("next")
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return None


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login() -> ResponseReturnValue:
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.session.scalar(db.select(User).where(User.username == username))
        # A mesma mensagem para usuário inexistente, inativo e senha errada:
        # distinguir os casos diria a quem tenta quais nomes existem.
        if user is None or not user.is_active_user or not user.check_password(password):
            flash("Usuário ou senha inválidos.", "error")
            return render_template("auth/login.html", username=username), 401
        login_user(user, remember=True)
        return redirect(_safe_next_url() or url_for("web.dashboard"))

    return render_template("auth/login.html", username="")


@bp.post("/logout")
@login_required
def logout() -> ResponseReturnValue:
    logout_user()
    flash("Sessão encerrada.", "success")
    return redirect(url_for("web.login"))
