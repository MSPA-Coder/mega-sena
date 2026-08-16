# syntax=docker/dockerfile:1.7
#
# Imagem única para uso local: gunicorn, usuário não-root e sem ferramentas
# de teste. Migrações nunca rodam durante o build nem dentro de `create_app()`;
# docker-entrypoint.sh aplica `flask db upgrade` antes do servidor iniciar.

# -----------------------------------------------------------------------
# base: certificados locais opcionais, sem ferramentas de banco no runtime.
# -----------------------------------------------------------------------
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN --mount=type=secret,id=local_ca,required=false \
    if [ -f /run/secrets/local_ca ]; then \
        cp /run/secrets/local_ca /usr/local/share/ca-certificates/local-root-ca.crt; \
        update-ca-certificates; \
    fi

# -----------------------------------------------------------------------
# builder: instala as dependências Python em um venv isolado.
# -----------------------------------------------------------------------
FROM base AS builder

COPY requirements.txt ./
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN pip install --no-cache-dir -r requirements.txt

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
COPY --chown=mega_sena:mega_sena requirements.txt requirements-dev.txt pyproject.toml ./
COPY --chown=mega_sena:mega_sena tests ./tests
RUN pip install --no-cache-dir -r requirements-dev.txt
USER mega_sena

ENV RUFF_CACHE_DIR=/tmp/ruff-cache \
    PYTEST_ADDOPTS="-o cache_dir=/tmp/pytest-cache"
ENTRYPOINT []
CMD ["sh", "-c", "ruff check . && pytest"]
