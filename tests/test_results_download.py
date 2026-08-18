from __future__ import annotations

import socket

import pytest

from app.draws.downloading import (
    DEFAULT_RESULTS_SOURCE_URL,
    ResultsDownloadError,
    _ensure_public_host,
    normalize_results_source_url,
)


def test_default_results_source_url_is_valid_https_url():
    assert normalize_results_source_url(DEFAULT_RESULTS_SOURCE_URL) == DEFAULT_RESULTS_SOURCE_URL


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/results.xlsx",
        "https://user:password@example.com/results.xlsx",
        "https://example.com:8443/results.xlsx",
        "https://example.com/results.xlsx#fragment",
        "not a url",
    ],
)
def test_results_source_url_rejects_unsafe_or_invalid_urls(url: str):
    with pytest.raises(ValueError):
        normalize_results_source_url(url)


def test_results_source_url_rejects_private_destination(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    )

    with pytest.raises(ResultsDownloadError, match="servidor público"):
        _ensure_public_host("https://example.com/results.xlsx")
