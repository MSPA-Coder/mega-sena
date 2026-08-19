from __future__ import annotations

from werkzeug.middleware.proxy_fix import ProxyFix

from app import create_app


def test_proxy_configuration_accepts_the_deployment_host(monkeypatch):
    monkeypatch.setenv("MEGA_SENA_TRUSTED_HOSTS", "megasena-mspa.duckdns.org")
    monkeypatch.setenv("MEGA_SENA_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("MEGA_SENA_FORCE_HTTPS", "true")

    app = create_app(
        {
            "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://test:test@localhost:5432/test",
            "SECRET_KEY": "chave-de-teste-nao-usada-em-execucao-real",
            "TESTING": True,
        }
    )

    assert app.config["TRUSTED_HOSTS"] == ["megasena-mspa.duckdns.org"]
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert isinstance(app.wsgi_app, ProxyFix)
