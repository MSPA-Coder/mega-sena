"""Troca da própria senha.

Fica fora de `users.py` de propósito: aquilo é administração de contas
alheias e exige `admin`; isto é a conta de quem está logado e não exige papel
nenhum. Juntar os dois num módulo só tornaria fácil errar o decorator.

A tela atende dois casos com o mesmo formulário:

- **voluntário** — a pessoa quis trocar a senha, chegou pelo menu;
- **obrigatório** — um administrador redefiniu a senha dela, e
  `requer_troca_de_senha` (registrado em `app/__init__.py`) prende a sessão
  aqui até a troca acontecer.

A diferença é só de apresentação: no caso obrigatório a navegação some, para
não oferecer links que o portão devolveria para cá de qualquer jeito.
"""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_user

from ..accounts.service import MIN_PASSWORD_LENGTH, change_own_password
from . import bp


@bp.route("/minha-senha", methods=["GET", "POST"])
def change_password() -> ResponseReturnValue:
    obrigatoria = bool(current_user.must_change_password)

    if request.method == "POST":
        try:
            change_own_password(
                current_user,
                request.form.get("current_password", ""),
                request.form.get("new_password", ""),
                request.form.get("password_confirm", ""),
            )
        except ValueError as exc:
            # Todas as recusas de `sharedauth.passwords.validar_troca` são
            # `ValueError`; a mensagem de cada uma já é adequada à pessoa.
            #
            # O erro fica no próprio cartão, não em `flash()`: é o mesmo POST
            # sendo respondido, sem redirect.
            return render_template(
                "account/change_password.html",
                obrigatoria=obrigatoria,
                erro=str(exc),
                min_password_length=MIN_PASSWORD_LENGTH,
            ), 400

        # Renova a sessão de quem acabou de trocar. O identificador no cookie
        # carrega a marca da senha ANTIGA (ver `User.get_id`), então sem isto a
        # pessoa seria deslogada pela própria troca -- o efeito que se quer é
        # derrubar as OUTRAS sessões, não esta. É o que
        # `update_session_auth_hash` faz no Django.
        login_user(current_user, remember=True)
        flash("Senha alterada.", "success")
        return redirect(url_for("web.dashboard"))

    return render_template(
        "account/change_password.html",
        obrigatoria=obrigatoria,
        erro=None,
        min_password_length=MIN_PASSWORD_LENGTH,
    )
