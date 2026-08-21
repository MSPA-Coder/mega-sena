# syntax=docker/dockerfile:1.7
#
# Imagem única para uso local: gunicorn, usuário não-root e sem ferramentas
# de teste. Migrações nunca rodam durante o build nem dentro de `create_app()`;
# docker-entrypoint.sh aplica `flask db upgrade` antes do servidor iniciar.

# -----------------------------------------------------------------------
# base: certificados locais opcionais, sem ferramentas de banco no runtime.
# -----------------------------------------------------------------------
FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Correcoes de seguranca da base e das ferramentas de empacotamento.
#
# `apt-get upgrade` porque a `python:3.14-slim` publicada carrega pacotes do
# Debian com CVE ja corrigido a montante; sem isto a correcao so chega quando a
# imagem oficial for republicada. O `setuptools` que vem na base tambem fica
# para tras -- o 70.3.0 tinha CVE-2025-47273, travessia de caminho.
#
# Achado pela varredura Trivy que entrou nesta mesma fase. Antes dela ninguem
# perguntava se a imagem que esta rodando tem CVE.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir --upgrade pip setuptools

RUN --mount=type=secret,id=local_ca,required=false \
    if [ -f /run/secrets/local_ca ]; then \
        cp /run/secrets/local_ca /usr/local/share/ca-certificates/local-root-ca.crt; \
        update-ca-certificates; \
    fi

# -----------------------------------------------------------------------
# builder: instala as dependências Python em um venv isolado.
#
# `requirements.txt` inclui `sharedauth` de um repositório Git privado
# (github.com/MSPA-Coder/SharedAuth) — pip precisa de `git` no PATH e de
# credencial para HTTPS. O secret `github_token` (BuildKit, nunca vira
# camada da imagem) autentica só para este RUN; `git config --unset` no
# fim da mesma instrução remove o token do `.gitconfig` antes de commitar
# a camada.
# -----------------------------------------------------------------------
FROM base AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN --mount=type=secret,id=github_token \
    git config --global url."https://x-access-token:$(cat /run/secrets/github_token)@github.com/".insteadOf "https://github.com/" && \
    pip install --no-cache-dir -r requirements.txt && \
    git config --global --unset url."https://x-access-token:$(cat /run/secrets/github_token)@github.com/".insteadOf

# -----------------------------------------------------------------------
# runtime: usuário não-root; o override local pode montar o código.
# -----------------------------------------------------------------------
FROM base AS runtime

ENV PATH="/opt/venv/bin:${PATH}"

RUN groupadd --system mega_sena \
    && useradd --system --gid mega_sena --home-dir /app --no-create-home mega_sena

COPY --from=builder /opt/venv /opt/venv
COPY --chown=mega_sena:mega_sena app ./app
COPY --chown=mega_sena:mega_sena migrations ./migrations
COPY --chown=mega_sena:mega_sena run.py ./
COPY --chmod=755 docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Tira `pip` e `setuptools` da imagem SERVIDA.
#
# Sao ferramenta de build e nao tem uso aqui -- e o mesmo raciocinio que ja
# mantem `gcc`, `make` e `wget` fora do runtime, o que os testes de contrato
# deste projeto verificam.
#
# Nao e higiene abstrata: a varredura de vulnerabilidade que entrou nesta fase
# acusou CVE-2025-47273 no `setuptools` e GHSA-6v7p-g79w-8964 no `msgpack` que
# o `pip` carrega vendorizado em `pip/_vendor/`. Nenhum dos dois chega a ser
# executado nesta imagem. Remover apaga as duas descobertas E a superficie,
# em vez de ficar perseguindo versao de pacote que ninguem invoca.
#
# Seguro por medicao, nao por suposicao: os quatro conteineres em producao ja
# rodavam sem `setuptools` antes desta mudanca.
#
# A ultima linha e a propria verificacao: se `pip` continuar no PATH, o build
# falha aqui em vez de entregar uma imagem que so parece limpa.
RUN set -eu; \
    for raiz in /usr/local/lib/python*/site-packages /opt/venv/lib/python*/site-packages; do \
      [ -d "$raiz" ] || continue; \
      rm -rf "$raiz"/pip "$raiz"/pip-*.dist-info \
             "$raiz"/setuptools "$raiz"/setuptools-*.dist-info \
             "$raiz"/pkg_resources "$raiz"/_distutils_hack \
             "$raiz"/wheel "$raiz"/wheel-*.dist-info; \
    done; \
    rm -f /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.* \
          /opt/venv/bin/pip /opt/venv/bin/pip3 /opt/venv/bin/pip3.*; \
    ! command -v pip

USER mega_sena

EXPOSE 5001
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--threads", "4", "--worker-class", "gthread", "--timeout", "60", "--worker-tmp-dir", "/tmp", "--no-control-socket", "run:app"]

# -----------------------------------------------------------------------
# quality: Ruff e a suíte mínima de segurança. Nunca é a imagem servida —
# `compose.yaml` usa `runtime`. O entrypoint é sobrescrito de propósito: o
# padrão aplicaria migrações no banco da aplicação antes de cada comando.
# -----------------------------------------------------------------------
FROM runtime AS quality

USER root
# O estágio `runtime` acima remove o `pip` da imagem. Este estágio herda dela e
# precisa dele de volta para instalar as dependências de teste. `ensurepip` é o
# mecanismo do próprio Python para isso, não uma gambiarra.
#
# A imagem SERVIDA continua sem `pip`: `quality` está atrás do profile do mesmo
# nome e nunca vai para produção.
RUN python -m ensurepip --upgrade \
    && python -m pip --version
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY --chown=mega_sena:mega_sena requirements.txt requirements-dev.txt pyproject.toml ./
COPY --chown=mega_sena:mega_sena tests ./tests
RUN --mount=type=secret,id=github_token \
    git config --global url."https://x-access-token:$(cat /run/secrets/github_token)@github.com/".insteadOf "https://github.com/" && \
    python -m pip install --no-cache-dir -r requirements-dev.txt && \
    git config --global --unset url."https://x-access-token:$(cat /run/secrets/github_token)@github.com/".insteadOf
USER mega_sena

ENV RUFF_CACHE_DIR=/tmp/ruff-cache \
    PYTEST_ADDOPTS="-o cache_dir=/tmp/pytest-cache"
ENTRYPOINT []
CMD ["sh", "-c", "ruff check . && pytest"]
