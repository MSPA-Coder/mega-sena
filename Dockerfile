# syntax=docker/dockerfile:1.7
#
# Imagem única para uso local: gunicorn, usuário não-root e sem ferramentas
# de teste. Migrações nunca rodam durante o build nem dentro de `create_app()`;
# docker-entrypoint.sh aplica `flask db upgrade` antes do servidor iniciar.

# -----------------------------------------------------------------------
# base: certificados locais opcionais, sem ferramentas de banco no runtime.
# -----------------------------------------------------------------------
# Base fixada por DIGEST do indice multi-arquitetura, e nao pela tag.
#
# `python:3.14-slim` e um alvo movel: a tag e reapontada a cada republicacao, e
# como o `deploy.sh` reconstroi no VPS, a imagem servida podia nascer de uma
# base diferente da que a CI varreu. O digest e o mesmo raciocinio que ja fixa
# as actions por SHA e o Trivy por digest.
#
# E digest de INDICE, nao de manifesto: assim continua valendo para amd64 e
# arm64. O Dependabot atualiza esta linha.
FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6 AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN --mount=type=secret,id=local_ca,required=false \
    if [ -f /run/secrets/local_ca ]; then \
        cp /run/secrets/local_ca /usr/local/share/ca-certificates/local-root-ca.crt; \
        update-ca-certificates; \
    fi

# Correcoes de seguranca da base e das ferramentas de empacotamento.
#
# `apt-get upgrade` porque a `python:3.14-slim` publicada carrega pacotes do
# Debian com CVE ja corrigido a montante; sem isto a correcao so chega quando a
# imagem oficial for republicada. O `setuptools` que vem na base tambem fica
# para tras -- o 70.3.0 tinha CVE-2025-47273, travessia de caminho.
#
# A atualizacao mantem a imagem alinhada aos avisos verificados pela varredura
# Trivy executada no pipeline.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir --upgrade pip setuptools

# -----------------------------------------------------------------------
# builder: instala as dependências Python em um venv isolado, a partir do
# `uv.lock`.
#
# POR QUE `uv` E NÃO `pip install .`: `pip` resolvia as faixas do
# `pyproject.toml` no instante do build, então dois builds do MESMO commit
# podiam produzir imagens diferentes -- e o `deploy.sh` reconstrói no VPS, de
# modo que a imagem servida nunca foi exatamente a que a CI testou. O
# `uv.lock` fixa versão e hash SHA-256 de cada dependência.
#
# O FLAG É `--locked`, E A DIFERENÇA IMPORTA. `--frozen` apenas usa o lock sem
# olhar o `pyproject.toml`: com o lock desatualizado ele sai com sucesso e
# instala as versões antigas, em silêncio. `--locked` confere se o lock ainda
# corresponde ao `pyproject.toml` e REPROVA quando alguém edita a declaração e
# esquece de rodar `uv lock`. Testado nos dois modos antes de escolher.
#
# POR QUE ISSO IMPORTA MAIS AQUI DO QUE NA MAIORIA DOS PROJETOS: `sharedauth`
# vem de repositório Git, e o lock o prende ao COMMIT, não à tag. A regra "tag
# publicada é imutável" continua valendo, mas deixou de ser a única coisa
# entre o build e uma surpresa.
#
# `git` continua necessário: é assim que o `sharedauth` é obtido. O que saiu
# foi o token -- o repositório é público e a credencial era herança da época
# em que não era.
#
# `--no-editable` instala o projeto de verdade no venv, como `pip install .`
# fazia; sem isso o `uv` deixaria um link para a árvore de código, que o
# estágio `runtime` não copia.
# -----------------------------------------------------------------------
FROM base AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Versão fixa: o instalador que garante reprodutibilidade não pode ser ele
# próprio uma variável. O binário é autocontido e o estágio `quality` o copia
# daqui, em vez de reinstalá-lo.
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade "uv==0.12.10"

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
COPY pyproject.toml uv.lock README.md ./
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

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
# A remocao reduz a superficie de vulnerabilidades do runtime, inclusive a de
# pacotes vendorizados por `pip`, sem retirar ferramentas usadas pela aplicacao.
#
# A ultima linha e a propria verificacao: se `pip` continuar no PATH, o build
# falha aqui em vez de entregar uma imagem que so parece limpa.
#
# O `python -m pip check` que abria este bloco saiu com a adocao do `uv`. Ele
# perguntava se as dependencias instaladas sao mutuamente compativeis -- e o
# venv criado pelo `uv` nem tem `pip` para responder. A pergunta tambem deixou
# de fazer sentido: o conjunto vem resolvido do `uv.lock`, entao a coerencia e
# garantida na resolucao, e nao conferida depois da instalacao.
RUN set -eu; \
    for raiz in /usr/local/lib/python*/site-packages /opt/venv/lib/python*/site-packages; do \
      [ -d "$raiz" ] || continue; \
      rm -rf "$raiz"/pip "$raiz"/pip-*.dist-info \
             "$raiz"/setuptools "$raiz"/setuptools-*.dist-info \
             "$raiz"/pkg_resources "$raiz"/_distutils_hack \
             "$raiz"/distutils-precedence.pth \
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
# O `ensurepip` que existia aqui saiu junto com o `pip`: o estágio `runtime`
# remove o `pip` da imagem, e este herdava dela, então precisava reinstalá-lo
# só para poder instalar as dependências de teste.
#
# Com o `uv` isso deixa de ser necessário -- ele é um binário autocontido, e
# copiá-lo do `builder` é mais barato e mais previsível do que reinstalar um
# gerenciador de pacotes. A imagem SERVIDA continua sem `pip` e sem `uv`:
# `quality` está atrás do profile do mesmo nome e nunca vai para produção.
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
COPY --chown=mega_sena:mega_sena pyproject.toml uv.lock README.md ./
COPY --chown=mega_sena:mega_sena tests ./tests
# `--extra dev` acrescenta as ferramentas de teste ao MESMO venv que o runtime
# usa, em vez de montar outro: a suíte tem de medir exatamente o que a imagem
# servida instala, e o lock garante que sejam as mesmas versões.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable --extra dev
USER mega_sena

ENV RUFF_CACHE_DIR=/tmp/ruff-cache \
    PYTEST_ADDOPTS="-o cache_dir=/tmp/pytest-cache"
ENTRYPOINT []
CMD ["sh", "-c", "ruff check . && pytest"]
