from __future__ import annotations

import re
from io import BytesIO  # noqa: F401
from pathlib import Path  # noqa: F401
from zipfile import ZIP_DEFLATED, ZipFile  # noqa: F401

import pytest  # noqa: F401

from app import create_app, db  # noqa: F401
from app.models import Config, Draw  # noqa: F401
from app.bets.combinatorics import (  # noqa: F401
    build_combination_report,
    calculate_individual_filter_targets,
    count_draws_matching_filters,
    count_possible_draw_combinations,
)
from app.bets.service import (  # noqa: F401
    generate_closure_bets,
    list_recent_generations,
    list_recent_generations_with_bets,
    save_generated_bets,
)
from app.core.numbers import (  # noqa: F401
    count_consecutive_numbers,
    count_even_numbers,
    count_occupied_range_bands,
    draw_parameters,
    max_range_band_count,
)
from app.draws.importing import import_results_from_xlsx  # noqa: F401
from app.draws.statistics import (  # noqa: F401
    build_recent_frequency,
    build_stats,
    ensure_draw_parameters_current,
)
from app.settings.service import get_config_values  # noqa: F401
from tests.support import csrf_form_data, css_source, make_app, workbook_bytes  # noqa: F401


def test_css_manifest_references_existing_modules() -> None:
    manifest = Path("app/static/style.css").read_text(encoding="utf-8")
    imports = re.findall(r'@import url\("([^"]+)"\);', manifest)

    assert imports
    assert all((Path("app/static") / relative_path).is_file() for relative_path in imports)


def test_generated_bets_use_two_column_grid() -> None:
    css = css_source()
    template = Path("app/templates/bets/index.html").read_text(encoding="utf-8")

    assert template.count('class="generated-bets-grid"') == 2
    assert ".generated-bets-grid" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css
    ball_rule_start = css.index(".generated-bets-grid .bet-line .ball {")
    ball_rule_end = css.index("}", ball_rule_start)
    assert "color: #fff" in css[ball_rule_start:ball_rule_end]


def test_theme_toggle_button_is_present_on_every_page() -> None:
    """O controle de tema deve existir e funcionar (cookie 'theme' já era lido, mas sem controle visível)."""
    app = make_app()
    with app.app_context():
        db.create_all()

    text = app.test_client().get("/dashboard").get_data(as_text=True)

    assert 'id="theme-toggle"' in text
    assert "data-theme=" in text


def test_destructive_reset_button_uses_danger_styling_not_secondary() -> None:
    """A ação destrutiva de apagar a base deve ter estilo visual distinto (danger), não genérico (secondary)."""
    app = make_app()
    with app.app_context():
        db.create_all()

    text = app.test_client().get("/settings").get_data(as_text=True)
    danger_button_start = text.index("Apagar concursos e apostas")
    button_tag = text[max(0, danger_button_start - 200):danger_button_start]

    assert "danger" in button_tag
    assert "data-confirm-message" in button_tag
    assert "onclick=" not in button_tag


def test_css_defines_distinct_secondary_and_danger_button_styles() -> None:
    """.secondary não deve mais ser idêntico ao botão primário; .danger deve existir."""
    css = css_source()

    assert ".button.danger" in css
    secondary_rule_start = css.index(".button.secondary,")
    secondary_rule_end = css.index("}", secondary_rule_start)
    secondary_rule = css[secondary_rule_start:secondary_rule_end]
    # O estilo "secondary" não deve mais usar a cor de fundo do botão primário.
    assert "background: var(--button-bg)" not in secondary_rule


def test_css_defines_design_tokens_for_typography_and_radius() -> None:
    """A folha de estilo deve declarar as fontes e a escala de raio usadas na revisão de UX."""
    css = css_source()

    assert "--font-display" in css
    assert "--font-mono" in css
    assert "--radius-sm" in css
    assert "--radius-md" in css
    assert "--radius-lg" in css
    assert "Space Grotesk" in css
    assert "JetBrains Mono" in css


def test_dashboard_heading_no_longer_has_stray_numeric_prefix() -> None:
    """O título 'Distribuição por faixas' não deve mais ter o prefixo solto '5.'."""
    app = make_app()
    with app.app_context():
        db.create_all()

    text = app.test_client().get("/dashboard").get_data(as_text=True)

    assert "<h3>Distribuição por faixas</h3>" in text
    assert "5. Distribuição por faixas" not in text


def test_static_css_link_has_cache_busting_version() -> None:
    """O link do style.css deve ter ?v=<versão> para o navegador nunca servir uma cópia velha do cache."""
    app = make_app()
    with app.app_context():
        db.create_all()

    text = app.test_client().get("/dashboard").get_data(as_text=True)

    assert "style.css?v=" in text


def test_frequency_card_ball_spacing_uses_margin_not_only_gap() -> None:
    """
    O espaçamento bola->rótulo nos cards Mais/Menos frequentes não deve depender
    só de 'gap' do flexbox: precisa de uma margem explícita como reforço, para
    garantir o espaçamento mesmo se 'gap' não for respeitado pelo navegador.
    """
    css = css_source()

    rule_start = css.index(".dashboard-frequency-stacked .frequency-item .ball {")
    rule_end = css.index("}", rule_start)
    rule = css[rule_start:rule_end]

    assert "margin-right" in rule
    # Garante que a margem aplicada é claramente maior que o espaçamento original (4px).
    match = re.search(r"margin-right:\s*(\d+)px", rule)
    assert match is not None
    assert int(match.group(1)) >= 16


def test_nav_tab_renamed_from_importar_to_configuracoes() -> None:
    """O link de navegação deve mostrar 'Configurações', não mais 'Importar'."""
    app = make_app()
    with app.app_context():
        db.create_all()

    text = app.test_client().get("/dashboard").get_data(as_text=True)

    assert ">Configurações</a>" in text
    assert ">Importar</a>" not in text
    assert 'href="/settings"' in text


def test_primary_nav_has_accessible_mobile_toggle() -> None:
    """O menu principal deve ter botão colapsável acessível para telas pequenas."""
    app = make_app()
    with app.app_context():
        db.create_all()

    text = app.test_client().get("/dashboard").get_data(as_text=True)

    assert 'id="nav-toggle"' in text
    assert 'aria-controls="primary-nav"' in text
    assert 'aria-expanded="false"' in text
    assert 'id="primary-nav"' in text
    assert 'aria-label="Navegação principal"' in text


def test_save_settings_and_reset_redirect_to_settings_page() -> None:
    """Salvar configurações e resetar a base devem continuar redirecionando para a página /settings."""
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.post("/settings", data=csrf_form_data(client, "/settings", {"bet_quantity": "6"}), follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/settings")

    response = client.post("/reset", data=csrf_form_data(client, "/settings"), follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"] == "/settings"


def test_upload_endpoint_redirects_back_to_contests_on_every_outcome() -> None:
    """Sucesso ou falha no upload, o usuário deve voltar para /contests (onde o form vive)."""
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.post("/contests/import", data=csrf_form_data(client, "/contests"), follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"] == "/contests"


def test_panel_header_pattern_is_shared_across_pages() -> None:
    """A classe .panel-header (tema herdado de Concursos) deve aparecer em várias abas, não só em uma."""
    app = make_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    contests_text = client.get("/contests").get_data(as_text=True)
    settings_text = client.get("/settings").get_data(as_text=True)
    bets_text = client.get("/bets").get_data(as_text=True)
    rationale_text = client.get("/rationale").get_data(as_text=True)

    assert "panel-header" in contests_text
    assert "panel-header" in settings_text
    assert "panel-header" in bets_text
    assert "panel-header" in rationale_text


def test_dashboard_has_page_title_matching_other_tabs() -> None:
    """O Dashboard não tinha título de página; agora deve ter, como as demais abas."""
    app = make_app()
    with app.app_context():
        db.create_all()

    text = app.test_client().get("/dashboard").get_data(as_text=True)

    assert "<h2>Dashboard</h2>" in text


def test_generate_bets_button_is_primary_not_secondary() -> None:
    """
    Regressão: 'Gerar Apostas' é a ação principal da tela e não deve usar a classe
    'secondary' (bug encontrado durante a harmonização: estava marcado como secundário).
    """
    app = make_app()
    with app.app_context():
        db.create_all()

    text = app.test_client().get("/bets").get_data(as_text=True)
    button_start = text.rindex("<button", 0, text.index('value="generate"'))
    button_end = text.index(">", text.index('value="generate"'))
    button_tag = text[button_start:button_end]

    assert "secondary" not in button_tag


def test_css_defines_semantic_tint_tokens() -> None:
    """As cores de tinta (positivo/aviso/dourado) devem existir nos dois temas."""
    css = css_source()

    assert "--surface-tint-positive" in css
    assert "--surface-tint-warm" in css
    assert "--surface-tint-gold" in css
    assert ".tint-positive" in css
    assert ".tint-warm" in css
    assert ".tint-gold" in css


def test_dashboard_frequency_cards_use_semantic_tints() -> None:
    """Mais frequentes/Menos frequentes/Acertadores devem ter cor própria, não brancos neutros."""
    app = make_app()
    with app.app_context():
        db.create_all()

    text = app.test_client().get("/dashboard").get_data(as_text=True)

    acertadores_start = text.index('id="dash-acertadores-card"')
    acertadores_tag = text[max(0, acertadores_start - 120):acertadores_start]
    assert "tint-gold" in acertadores_tag

    most_idx = text.index("Mais frequentes")
    most_card_tag = text[max(0, most_idx - 150):most_idx]
    assert "tint-positive" in most_card_tag

    least_idx = text.index("Menos frequentes")
    least_card_tag = text[max(0, least_idx - 150):least_idx]
    assert "tint-warm" in least_card_tag


def test_repeated_row_lists_have_zebra_striping() -> None:
    """
    As listas repetidas do app (pares, faixas, apostas de uma geração, lista de
    gerações, etapas de filtro) devem ter zebra, espelhando o tema de Concursos.
    """
    css = css_source()

    assert ".compact-stats p:nth-child(even)" in css
    assert ".range-band-list p:nth-child(4n+3)" in css
    assert ".bet-line:nth-child(even)" in css
    assert ".generation-group:nth-child(even) .generation-line" in css
    assert ".combination-filter-list p:nth-child(even)" in css


def test_generation_list_zebra_targets_correct_alternating_element() -> None:
    """
    Regressão: cada .generation-line vive dentro do seu próprio .generation-group,
    então ':nth-child(even)' direto em .generation-line nunca alternava (sempre
    era o 1º filho do seu grupo). A zebra precisa alternar por .generation-group.
    """
    app = make_app()
    with app.app_context():
        db.create_all()
        from app.bets.service import generate_bets, save_generated_bets

        for _ in range(3):
            bets = generate_bets(6, 2, persist=False)
            save_generated_bets(6, [b.numbers_csv for b in bets])

    text = app.test_client().get("/bets").get_data(as_text=True)

    assert text.count("generation-group") >= 3
