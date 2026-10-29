"""HTTP/DNS controlados; o downloader e seus limites executam integralmente."""

import socket
from email.message import Message
from io import BytesIO
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

from app.draws import downloading as d


def resposta(conteudo=b"PK-planilha-sintetica", tipo="application/xlsx", tamanho=None):
    stream = BytesIO(conteudo)
    stream.headers = Message()
    stream.headers["Content-Type"] = tipo
    if tamanho is not None:
        stream.headers["Content-Length"] = str(tamanho)
    return stream


@pytest.fixture
def rede(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))])
    opener = Mock()
    monkeypatch.setattr(d, "build_opener", Mock(return_value=opener))
    return opener


def test_download_le_stream_fecha_resposta_e_volta_ao_inicio(rede):
    http = resposta()
    rede.open.return_value = http
    arquivo = d.fetch_results_xlsx(d.DEFAULT_RESULTS_SOURCE_URL)
    assert arquivo.tell() == 0
    assert arquivo.read() == b"PK-planilha-sintetica"
    assert http.closed
    assert rede.open.call_args.kwargs["timeout"] == 20


@pytest.mark.parametrize("http", [resposta(tipo="text/html"), resposta(tamanho="inválido"),
                                   resposta(tamanho=d.MAX_REMOTE_DOWNLOAD_BYTES + 1),
                                   resposta(b"x" * (d.MAX_REMOTE_DOWNLOAD_BYTES + 1))])
def test_mime_tamanho_invalido_ou_stream_excessivo_nao_chegam_ao_importador(rede, http):
    rede.open.return_value = http
    with pytest.raises(d.ResultsDownloadError):
        d.fetch_results_xlsx(d.DEFAULT_RESULTS_SOURCE_URL)
    assert http.closed


def test_redirecionamento_a_rede_privada_e_bloqueado_antes_de_nova_requisicao(rede):
    erro = HTTPError(d.DEFAULT_RESULTS_SOURCE_URL, 302, "Found", {"Location": "https://127.0.0.1/dados"}, BytesIO())
    rede.open.side_effect = erro
    with pytest.raises(ValueError):
        d.fetch_results_xlsx(d.DEFAULT_RESULTS_SOURCE_URL)
    assert rede.open.call_count == 1


@pytest.mark.parametrize("erro", [URLError("indisponível"), HTTPError(d.DEFAULT_RESULTS_SOURCE_URL, 403, "Forbidden", {}, BytesIO())])
def test_erros_de_rede_viram_falha_de_download(rede, erro):
    rede.open.side_effect = erro
    with pytest.raises(d.ResultsDownloadError):
        d.fetch_results_xlsx(d.DEFAULT_RESULTS_SOURCE_URL)


def test_redirecionamento_oficial_revalida_e_tem_limite(rede):
    def redirecionar(*args, **kwargs):
        raise HTTPError(d.DEFAULT_RESULTS_SOURCE_URL, 302, "Found", {"Location": "/outro.xlsx"}, BytesIO())

    rede.open.side_effect = redirecionar
    with pytest.raises(d.ResultsDownloadError):
        d.fetch_results_xlsx(d.DEFAULT_RESULTS_SOURCE_URL)
    assert rede.open.call_count == d.MAX_REDIRECTS + 1
