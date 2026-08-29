# Desenvolvimento e validação

O projeto usa Docker para aplicação, PostgreSQL, migrations, lint e testes. No
host são necessários apenas Docker Desktop, Git e um editor.

## Ambiente

```powershell
Copy-Item .env.docker.example .env.docker
.\scripts\provision_secrets.ps1
.\scripts\export_local_ca.ps1
docker compose --env-file .env.docker -f compose.yaml -f compose.dev.yaml up --build -d
```

`provision_secrets.ps1` cria, sem exibir os valores,
`.secrets/postgres_password.txt` e `.secrets/secret_key.txt`. Se um ambiente
antigo ainda tiver `POSTGRES_PASSWORD` ou `SECRET_KEY` no `.env.docker`, o
script pode migrá-los para arquivos; use `-RemoveLegacyValues` somente depois
de validar a subida. `-Force` troca os segredos e exige tratar a senha do banco
e a invalidação das sessões existentes.

Sem `compose.dev.yaml`, o serviço usa a imagem imutável. O entrypoint executa
`flask --app run.py db upgrade` antes do Gunicorn; `create_app()` apenas monta a
aplicação e não consulta o banco, cria tabelas ou dados iniciais.

## Validação automatizada

O comando oficial executa Ruff e toda a suíte pytest na imagem `quality`:

```powershell
docker compose --env-file .env.docker -f compose.yaml --profile quality run --build --rm quality
```

**`--build` não é opcional.** O serviço `quality` não monta o código do
host: o que ele executa é o que foi copiado para a imagem. `docker compose
run` reconstrói apenas quando a imagem não existe — se ela já existe, o
comando roda a versão anterior do código e passa em verde sem ter visto
nenhuma das suas alterações. É uma falha silenciosa na direção pior: dá
confiança sem dar evidência. O CI não corre esse risco porque reconstrói
sem cache antes de executar; o comando local precisa do `--build` para ter
o mesmo significado.

A suíte protege os contratos HTTP e de segurança — autenticação por padrão,
CSRF, cabeçalhos, proxy, health check, download e limite de login —, a
integridade do grafo Alembic e a configuração de bootstrap. Os testes de
domínio cobrem, sem depender de uma quantidade total fixa de casos:

- normalização e limites dos critérios de geração, aplicação inclusiva dos
  filtros, rejeição de resultados já sorteados, diversidade do lote e ausência
  de persistência antes da confirmação;
- enumeração e validação dos fechamentos, identificação única de lote e
  atomicidade da gravação;
- inclusão, atualização e preservação de campos opcionais na importação de
  concursos, com rollback integral diante de metadado inválido.

Esses testes são contrato de regressão das regras centrais. Uma mudança nessas
regras deve atualizar implementação, testes e `docs/business-rules.md` na mesma
alteração.

O CI valida o Compose, reconstrói sem cache e executa o estágio `quality`. Ele
também audita as dependências Python instaladas com `pip-audit` e a imagem de
runtime com Trivy. O Dependabot acompanha dependências Python, imagens Docker e
GitHub Actions. Não há análise estática de tipos nem varredura CodeQL.

## Validação proporcional

Além do comando automatizado:

1. percorra no navegador o fluxo alterado;
2. em mudança de Docker ou dependências, reconstrua a imagem e confira a subida
   e os health checks;
3. em mudança de autenticação, sessão, autorização, CSRF ou proxy, exercite
   também login, logout e uma operação mutante;
4. em mudança persistente, gere e verifique um backup conforme
   `docs/deployment-vps.md`, aplique a cadeia completa em PostgreSQL vazio e
   teste upgrade e downgrade da revisão alterada.

## Schema

O schema evolui somente por novas revisões em `migrations/versions/`. Não
reescreva revisions já aplicáveis, não use `db.create_all()` como bootstrap e
não use `stamp` como substituto de uma migration. Consulte
[`migrations/README`](../migrations/README) para os comandos e a cadeia atual.
