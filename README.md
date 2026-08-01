# Mega Sena AI

Aplicação web para importar resultados da Mega-Sena, consultar estatísticas e
organizar apostas. Frequências e filtros descrevem o histórico carregado; não
preveem sorteios nem aumentam a probabilidade matemática de uma combinação.

## Recursos

- importação e atualização de concursos a partir de planilhas `.xlsx`;
- dashboard de frequências, somas, paridade, sequências e premiações;
- consulta de concursos com filtros;
- geração aleatória de apostas com critérios opcionais;
- fechamento completo de um conjunto de dezenas;
- relatório do universo combinatório e da cobertura calculada;
- revisão, gravação e consulta dos lotes de apostas;
- configuração dos valores iniciais da tela de geração.

## Início rápido com Docker

O ambiente Docker inclui a aplicação, PostgreSQL 17 e as ferramentas de
desenvolvimento. O host precisa somente de Docker Desktop, Git e GitHub CLI.
`docker compose up` já usa `compose.override.yaml` automaticamente: código
montado por bind mount e servidor de desenvolvimento do Flask.

```powershell
Copy-Item .env.docker.example .env.docker
.\scripts\export_local_ca.ps1
docker compose --env-file .env.docker up --build -d
```

A aplicação fica em <http://127.0.0.1:5001>. Os dados do PostgreSQL permanecem
no volume `postgres_data` quando os contêineres são interrompidos. Ao subir,
`docker-entrypoint.sh` aplica as migrações pendentes (`flask db upgrade`) e
garante a configuração padrão (`flask seed-defaults`) como uma etapa
controlada, antes de iniciar o servidor — a aplicação em si nunca faz isso por
conta própria (veja [Arquitetura](docs/architecture.md)).

```powershell
docker compose --env-file .env.docker down
```

`docker compose down -v` também remove o volume do banco; use essa opção somente
quando quiser descartar os dados.

Para construir a imagem de produção (`Dockerfile`, estágio `runtime`: gunicorn,
usuário não-root, sem bind mount), ignore o override de desenvolvimento:

```powershell
docker compose -f compose.yaml --env-file .env.docker up --build -d
```

O VS Code pode se conectar ao contêiner `app` com **Dev Containers: Reopen in
Container**.

## Dados existentes

Para copiar os dados de `instance/mega_sena.db` para o PostgreSQL do Docker:

```powershell
docker compose --env-file .env.docker --profile tools run --rm migrate
docker compose --env-file .env.docker exec app python -m scripts.verify_postgres
```

O comando `migrate` substitui os dados das tabelas da aplicação no PostgreSQL.
Ele preserva o arquivo SQLite e grava a conferência em
`migration_report.json`.

Para criar um backup do PostgreSQL:

```powershell
.\scripts\backup_postgres.ps1
```

Os arquivos são gravados em `instance/backups/`.

## Uso

1. Importe uma planilha em **Concursos**.
2. Explore o dashboard ou filtre os concursos carregados.
3. Em **Apostas**, escolha a quantidade de dezenas e os critérios, ou informe
   as dezenas-base de um fechamento.
4. Revise o resultado e grave somente os lotes que quiser conservar.
5. Ajuste os valores iniciais em **Configurações**.

O sistema é voltado ao uso local e individual e não possui autenticação. A
interface aceita de 6 a 20 dezenas, conforme a faixa oficial da Mega-Sena, e
até 100 apostas por geração. Veja as regras e as proteções operacionais em
[Regras funcionais](docs/business-rules.md).

## Verificação

A suíte de testes exige um PostgreSQL descartável definido em
`TEST_DATABASE_URL`; nenhum teste usa SQLite para simular persistência. A
suíte nunca aceita `DATABASE_URL` como alternativa, para não limpar o banco da
aplicação. O banco de teste precisa ter nome terminado em `_test`, ser distinto
de `DATABASE_URL` e somente as tabelas conhecidas da aplicação são limpas. No
ambiente Docker, o serviço `postgres` já expõe um banco descartável em
`127.0.0.1:${POSTGRES_PORT:-5433}` para isso:

```powershell
# Execute apenas na primeira vez, depois de subir o serviço postgres.
docker compose --env-file .env.docker exec -T postgres sh -c 'createdb -U "$POSTGRES_USER" mega_sena_test'
docker compose --env-file .env.docker run --rm --no-deps app sh -c `
  'export TEST_DATABASE_URL="${DATABASE_URL%/*}/mega_sena_test"; python -m pytest -q'
docker compose --env-file .env.docker run --rm --no-deps app python -m ruff check app migrations scripts tests run.py
docker compose --env-file .env.docker run --rm --no-deps app python scripts/audit_dependencies.py
```

O banco `mega_sena_test` é descartável: a suíte o limpa antes de cada teste.

O schema de teste é criado automaticamente (Alembic) na primeira vez que um
teste precisa de banco; testes unitários puros (`tests/unit/`) não tocam o
PostgreSQL. O CI executa Ruff e a suíte completa em Python 3.11 e 3.13 contra
PostgreSQL real, valida o fluxo de migração + seed + smoke transacional, e
executa a auditoria de dependências semanalmente ou por acionamento manual.

## Documentação

- [Arquitetura](docs/architecture.md)
- [Regras funcionais](docs/business-rules.md)
- [Desenvolvimento](docs/development.md)
- [Migrações](migrations/README)

## Estrutura

```text
app/
├── bets/          # critérios, geração e combinatória
├── core/          # utilitários e proteções HTTP
├── draws/         # importação, consultas e estatísticas
├── settings/      # preferências e manutenção dos dados
├── web/           # rotas e adaptação HTTP
├── static/        # JavaScript e CSS
├── templates/     # páginas e componentes Jinja
├── models.py
└── schema.py
docs/
migrations/
scripts/
tests/
```
