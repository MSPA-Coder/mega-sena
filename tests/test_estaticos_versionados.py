"""Este app instalou `sharedauth.estaticos`, e os templates o deixam agir."""

from __future__ import annotations

import re

from sharedauth.ui import UM_ANO_EM_SEGUNDOS


def test_login_referencia_estaticos_com_uma_versao_so(client):
    pagina = client.get("/login").get_data(as_text=True)
    referencias = re.findall(r'(?:href|src)="(/(?:static|sharedauth)/[^"]+)"', pagina)
    assert any("/static/style.css" in r for r in referencias)
    assert any("sharedauth-ui.js" in r for r in referencias)
    # Um `?v=` escrito à mão no template apareceria aqui como dois.
    for referencia in referencias:
        assert re.fullmatch(r"[^?]+\?v=[0-9a-f]{12}", referencia), referencia


def test_estatico_referenciado_vem_com_um_ano_de_cache(client):
    pagina = client.get("/login").get_data(as_text=True)
    url = re.search(r'href="(/static/style\.css[^"]*)"', pagina).group(1)
    cache = client.get(url).cache_control
    assert cache.max_age == UM_ANO_EM_SEGUNDOS
    assert cache.immutable
