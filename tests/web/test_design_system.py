from __future__ import annotations

import re
from pathlib import Path

from app import db
from tests.support import csrf_form_data, make_app


def test_css_manifest_references_existing_modules() -> None:
    manifest = Path("app/static/style.css").read_text(encoding="utf-8")
    imports = re.findall(r'@import url\("([^"]+)"\);', manifest)

    assert imports
    assert all(
        (Path("app/static") / relative_path).is_file() for relative_path in imports
    )


def test_theme_toggle_is_available() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    text = app.test_client().get("/dashboard").get_data(as_text=True)

    assert 'id="theme-toggle"' in text
    assert "data-theme=" in text


def test_destructive_reset_requires_confirmation_and_danger_styling() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    text = app.test_client().get("/settings").get_data(as_text=True)
    button_start = text.index("Apagar concursos e apostas")
    button_tag = text[max(0, button_start - 200) : button_start]

    assert "danger" in button_tag
    assert "data-confirm-message" in button_tag
    assert "onclick=" not in button_tag


def test_static_css_url_changes_with_asset_version() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    text = app.test_client().get("/dashboard").get_data(as_text=True)

    assert "style.css?v=" in text


def test_primary_navigation_is_accessible_and_links_main_pages() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    text = app.test_client().get("/dashboard").get_data(as_text=True)

    assert 'id="nav-toggle"' in text
    assert 'aria-controls="primary-nav"' in text
    assert 'aria-expanded="false"' in text
    assert 'id="primary-nav"' in text
    assert 'aria-label="Navegação principal"' in text
    for path in ("/dashboard", "/contests", "/bets", "/settings"):
        assert f'href="{path}"' in text


def test_settings_actions_return_to_settings_page() -> None:
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.post(
        "/settings",
        data=csrf_form_data(client, "/settings", {"bet_quantity": "6"}),
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/settings")

    response = client.post(
        "/reset",
        data=csrf_form_data(client, "/settings"),
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/settings"
