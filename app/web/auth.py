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
from sharedauth.access import url_proximo_seguro

from ..extensions import db
from ..models import User
from . import bp


def _safe_next_url() -> str | None:
    """Destino pós-login, lido de onde ele chega neste app.

    A decisão de segurança mora em `sharedauth.access.url_proximo_seguro` --
    era a mesma checagem escrita duas vezes, de dois jeitos, entre os apps
    Flask do mantenedor. Aqui fica só de onde o valor vem: `request.values`
    cobre a query da URL (o GET da tela) **e** o campo escondido do formulário
    (o POST).

    `request.args` sozinho era o defeito: o formulário posta em `/login` sem
    query nenhuma, então no POST -- o único momento em que o destino importa --
    o valor chegava sempre vazio, e todo login caía no dashboard. O teste que
    existia exercitava a função com um contexto montado à mão, nunca o POST de
    verdade, e por isso passava.
    """
    return url_proximo_seguro(request.values.get("next"))


@bp.route("/login", methods=["GET", "POST"])
def login() -> ResponseReturnValue:
    if current_user.is_authenticated:
        return redirect(url_for("web.dashboard"))

    # Lido uma vez, e devolvido ao formulário: o destino chega na query no GET
    # e no campo escondido no POST. Uma recusa de senha também precisa
    # carregá-lo adiante, senão a segunda tentativa perde o destino que a
    # primeira tinha.
    proximo = _safe_next_url()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.session.scalar(db.select(User).where(User.username == username))
        # A mesma mensagem para usuário inexistente, inativo e senha errada:
        # distinguir os casos diria a quem tenta quais nomes existem.
        #
        # Erro fica no próprio cartão (`erro=`), não em `flash()`: é o mesmo
        # POST que já está sendo respondido, sem redirect -- guardar na
        # sessão para reler na sequência seria um passo a mais sem motivo e
        # tiraria o erro do card estruturado da tela de login.
        if user is None or not user.is_active_user or not user.check_password(password):
            return render_template(
                "auth/login.html",
                username=username,
                erro="Usuário ou senha inválidos.",
                proximo=proximo,
            ), 401
        login_user(user, remember=True)
        return redirect(proximo or url_for("web.dashboard"))

    return render_template("auth/login.html", username="", proximo=proximo)


@bp.post("/logout")
@login_required
def logout() -> ResponseReturnValue:
    logout_user()
    flash("Sessão encerrada.", "success")
    return redirect(url_for("web.login"))
