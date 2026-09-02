from __future__ import annotations

import pytest
from werkzeug.middleware.proxy_fix import ProxyFix

from app import create_app

_CONFIG_BASE = {
    "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://test:test@localhost:5432/test",
    "SECRET_KEY": "chave-de-teste-nao-usada-em-execucao-real",
    "TESTING": True,
}


def test_proxy_configuration_accepts_the_deployment_host(monkeypatch):
    monkeypatch.setenv("MEGA_SENA_TRUSTED_HOSTS", "megasena-mspa.duckdns.org")
    monkeypatch.setenv("MEGA_SENA_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("MEGA_SENA_FORCE_HTTPS", "true")

    app = create_app(dict(_CONFIG_BASE))

    assert app.config["TRUSTED_HOSTS"] == ["megasena-mspa.duckdns.org"]
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert isinstance(app.wsgi_app, ProxyFix)


def test_host_publico_com_https_desligado_recusa_subir(monkeypatch):
    """MS-02: até 02/09/2026 essa combinação subia em silêncio, e o cookie de
    sessão saía sem `Secure` numa recriação do VPS que esquecesse `.env.vps`."""
    monkeypatch.setenv("MEGA_SENA_TRUSTED_HOSTS", "megasena-mspa.duckdns.org")
    monkeypatch.delenv("MEGA_SENA_FORCE_HTTPS", raising=False)

    with pytest.raises(RuntimeError, match="MEGA_SENA_TRUSTED_HOSTS.*MEGA_SENA_FORCE_HTTPS"):
        create_app(dict(_CONFIG_BASE))


def test_host_de_loopback_com_https_desligado_continua_funcionando(monkeypatch):
    # Desenvolvimento local em HTTP: o caminho padrão dos testes, sem variável
    # nenhuma definida -- TRUSTED_HOSTS cai no default de loopback.
    monkeypatch.delenv("MEGA_SENA_TRUSTED_HOSTS", raising=False)
    monkeypatch.delenv("MEGA_SENA_FORCE_HTTPS", raising=False)

    app = create_app(dict(_CONFIG_BASE))

    assert app.config["SESSION_COOKIE_SECURE"] is False
