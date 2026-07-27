# syntax=docker/dockerfile:1.7
#
# Multi-stage: `runtime` é a imagem imutável de produção (WSGI via gunicorn,
# usuário não-root, sem ferramentas de build/teste). `dev` é usada apenas
# pelo compose.override.yaml (bind mount do código, servidor de
# desenvolvimento do Flask). Migrações nunca rodam durante o build nem dentro
# de `create_app()`: docker-entrypoint.sh aplica `flask db upgrade` e
# `flask seed-defaults` como etapa controlada, sempre antes de iniciar o
# processo do servidor (runtime ou dev). Veja docs/architecture.md.

# -----------------------------------------------------------------------
# base: dependências de sistema comuns a build e runtime
# -----------------------------------------------------------------------
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN --mount=type=secret,id=local_ca,required=false \
    if [ -f /run/secrets/local_ca ]; then \
        cp /run/secrets/local_ca /usr/local/share/ca-certificates/local-root-ca.crt; \
    fi \
    && apt-get update \
    && apt-get install --no-install-recommends -y postgresql-client \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------
# builder / builder-dev: instalam dependências Python em um venv isolado,
# para que a imagem final não carregue ferramentas de build
# -----------------------------------------------------------------------
FROM base AS builder

COPY requirements.txt ./
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN pip install --no-cache-dir -r requirements.txt

FROM builder AS builder-dev

COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# -----------------------------------------------------------------------
# runtime: imagem de produção — imutável, usuário não-root, sem bind mount
# -----------------------------------------------------------------------
FROM base AS runtime

ENV PATH="/opt/venv/bin:${PATH}"

RUN groupadd --system mega_sena \
    && useradd --system --gid mega_sena --home-dir /app --no-create-home mega_sena

COPY --from=builder /opt/venv /opt/venv
COPY --chown=mega_sena:mega_sena . .
COPY --chmod=755 docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

USER mega_sena

EXPOSE 5000
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "60", "run:app"]

# -----------------------------------------------------------------------
# dev: imagem de desenvolvimento — ferramentas de teste/lint; o código real
# é sobreposto por bind mount em compose.override.yaml
# -----------------------------------------------------------------------
FROM base AS dev

ENV PATH="/opt/venv/bin:${PATH}"

COPY --from=builder-dev /opt/venv /opt/venv
COPY . .
COPY --chmod=755 docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "run.py"]
