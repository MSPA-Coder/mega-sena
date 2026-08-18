"""Download seguro da planilha pública de resultados."""

from __future__ import annotations

import ipaddress
import socket
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

DEFAULT_RESULTS_SOURCE_URL = (
    "https://servicebus3.caixa.gov.br/portaldeloterias/api/resultados/download?"
    "modalidade=Mega-Sena"
)
MAX_REMOTE_DOWNLOAD_BYTES = 10 * 1024 * 1024
MAX_REDIRECTS = 3
_ALLOWED_CONTENT_TYPES = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/xlsx",
    }
)


class ResultsDownloadError(RuntimeError):
    """A fonte configurada não entregou uma planilha segura para importação."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def normalize_results_source_url(value: object) -> str:
    """Normaliza uma URL HTTPS externa que possa fornecer a planilha."""
    url = str(value or "").strip()
    if not url or len(url) > 200:
        raise ValueError("Informe um link HTTPS de até 200 caracteres.")

    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("O link da planilha deve ser uma URL HTTPS pública válida.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("O link da planilha possui uma porta inválida.") from exc
    if port not in (None, 443):
        raise ValueError("O link da planilha deve usar a porta HTTPS padrão.")

    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def _ensure_public_host(url: str) -> None:
    hostname = urlsplit(url).hostname
    if hostname is None:
        raise ResultsDownloadError("O link configurado não possui um host válido.")
    try:
        addresses = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ResultsDownloadError("Não foi possível localizar o servidor da planilha.") from exc

    if not addresses or any(
        not ipaddress.ip_address(address[4][0]).is_global for address in addresses
    ):
        raise ResultsDownloadError("O link da planilha deve apontar para um servidor público.")


def fetch_results_xlsx(url: object) -> BytesIO:
    """Baixa uma planilha XLSX com limite, HTTPS e destino público.

    Nenhuma transação de banco fica aberta durante a chamada externa. Redirecionamentos
    são seguidos manualmente para validar cada destino e evitar que um link editável
    alcance a rede interna da aplicação.
    """
    current_url = normalize_results_source_url(url)
    opener = build_opener(_NoRedirect())

    for _ in range(MAX_REDIRECTS + 1):
        _ensure_public_host(current_url)
        request = Request(current_url, headers={"User-Agent": "MegaSena/1.0"})
        try:
            response = opener.open(request, timeout=20)
        except HTTPError as exc:
            if 300 <= exc.code < 400 and exc.headers.get("Location"):
                current_url = normalize_results_source_url(
                    urljoin(current_url, exc.headers["Location"])
                )
                exc.close()
                continue
            raise ResultsDownloadError("A fonte configurada recusou o download da planilha.") from exc
        except URLError as exc:
            raise ResultsDownloadError("Não foi possível acessar a fonte configurada.") from exc

        with response:
            content_type = response.headers.get_content_type().lower()
            if content_type not in _ALLOWED_CONTENT_TYPES:
                raise ResultsDownloadError("A fonte configurada não retornou uma planilha XLSX.")
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    declared_size = int(content_length)
                except ValueError as exc:
                    raise ResultsDownloadError(
                        "A fonte configurada informou um tamanho de arquivo inválido."
                    ) from exc
                if declared_size > MAX_REMOTE_DOWNLOAD_BYTES:
                    raise ResultsDownloadError("A planilha remota ultrapassa o limite de 10 MB.")

            content = BytesIO()
            while chunk := response.read(64 * 1024):
                if content.tell() + len(chunk) > MAX_REMOTE_DOWNLOAD_BYTES:
                    raise ResultsDownloadError("A planilha remota ultrapassa o limite de 10 MB.")
                content.write(chunk)
            content.seek(0)
            return content

    raise ResultsDownloadError("A fonte configurada redirecionou vezes demais.")
