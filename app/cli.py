"""Comandos de linha registrados na aplicacao.

`criar-usuario` existe porque a aplicacao nega por padrao: sem ele, uma
instalacao nova ficaria inacessivel para sempre antes de existir sessao para
abrir a tela /usuarios. Continua util para provisionamento sem navegador.
"""

from __future__ import annotations

import click
from flask import Flask

from .accounts.service import MIN_PASSWORD_LENGTH
from .extensions import db
from .models import User


def register_commands(app: Flask) -> None:
    @app.cli.command("criar-usuario")
    @click.option("--usuario", prompt=True, help="Nome de usuario para o login.")
    @click.option(
        "--senha",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="Senha; solicitada de forma oculta se omitida.",
    )
    def criar_usuario(usuario: str, senha: str) -> None:
        """Cria um usuario ou redefine a senha de um existente."""
        usuario = usuario.strip()
        if not usuario:
            raise click.ClickException("O nome de usuario nao pode ser vazio.")
        if len(senha) < MIN_PASSWORD_LENGTH:
            raise click.ClickException(
                f"A senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres."
            )

        existente = db.session.scalar(db.select(User).where(User.username == usuario))
        if existente is None:
            novo = User(username=usuario, is_active_user=True)
            novo.set_password(senha)
            db.session.add(novo)
            acao = "criado"
        else:
            existente.set_password(senha)
            existente.is_active_user = True
            acao = "atualizado"
        db.session.commit()
        click.echo(f"Usuario '{usuario}' {acao}.")
