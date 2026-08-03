# Desenvolvimento

## Ambiente de desenvolvimento

O projeto é container-first: Python, dependências, PostgreSQL, migrações,
testes e verificações rodam nos serviços Docker. O host mantém Docker Desktop,
Git, GitHub CLI e o editor.

```powershell
Copy-Item .env.docker.example .env.docker
.\scripts\export_local_ca.ps1
docker compose --env-file .env.docker up --build -d
```

A aplicação fica em <http://127.0.0.1:5001>. No VS Code, **Dev Containers:
Reopen in Container** usa o mesmo contêiner `app`.

`docker-entrypoint.sh` aplica `flask db upgrade` e `flask seed-defaults` antes
de iniciar a aplicação. `create_app()` não migra nem grava dados por conta
própria (veja [Arquitetura](architecture.md)).

## Qualidade

A suíte de testes exige um PostgreSQL descartável definido em
`TEST_DATABASE_URL`; nenhum teste usa SQLite para simular persistência. A
suíte nunca usa `DATABASE_URL` como alternativa, para não limpar o banco da
aplicação. A URL de teste precisa identificar um banco distinto cujo nome
termine em `_test`; a limpeza é restrita às tabelas conhecidas da aplicação.
Testes puros de `tests/unit/` não tocam o banco.

No Docker, aponte para o banco descartável exposto pelo serviço `postgres`:

```powershell
# Execute apenas na primeira vez, depois de subir o serviço postgres.
docker compose --env-file .env.docker exec -T postgres sh -c 'createdb -U "$POSTGRES_USER" mega_sena_test'
docker compose --env-file .env.docker run --rm --no-deps app sh -c `
  'export TEST_DATABASE_URL="${DATABASE_URL%/*}/mega_sena_test"; python -m pytest -q'
docker compose --env-file .env.docker run --rm --no-deps app python -m ruff check app migrations scripts tests run.py
```

O banco `mega_sena_test` é descartável: a suíte o limpa antes de cada teste.

A auditoria de dependências de runtime é:

```powershell
docker compose --env-file .env.docker run --rm --no-deps app python scripts/audit_dependencies.py
```

O CI executa Ruff e a suíte completa em Python 3.11 e 3.13 contra PostgreSQL
real, valida o fluxo de migração + seed + smoke transacional, e verifica as
dependências semanalmente ou por acionamento manual.

## Testes

```text
tests/unit/          regras puras e normalização
tests/integration/   persistência, migrações, importação e serviços
tests/web/           contratos HTTP, formulários, navegação e segurança
```

Um teste deve proteger um comportamento atual ou um risco relevante:

- teste a regra no nível mais baixo que ofereça confiança;
- prefira entradas e resultados observáveis a detalhes internos;
- preserve cobertura de integridade, segurança e contratos usados pela
  interface;
- use testes web quando a mudança envolver fluxo, formulário, acessibilidade ou
  API;
- atualize ou remova o teste quando o requisito correspondente mudar.

Estrutura de arquivos, textos incidentais e detalhes visuais só devem ser
fixados por testes quando forem parte deliberada do contrato do produto.
Fixtures e builders compartilhados ficam em `tests/conftest.py` e
`tests/support.py`.

## Migrações

Depois de alterar um modelo, gere e revise a revisão no contêiner:

```powershell
docker compose --env-file .env.docker exec app flask --app run.py db migrate -m "descrição"
docker compose --env-file .env.docker exec app flask --app run.py db upgrade
```

Revise nulabilidade, tipos, índices, valores padrão e transformações de dados no
arquivo gerado. Uma revisão que possa ter sido aplicada em outro banco não deve
ser reescrita para representar um novo estado; crie uma revisão subsequente.

Migrações são aplicadas por uma etapa controlada e separada (`flask db
upgrade`), nunca automaticamente pela aplicação — veja
[Arquitetura](architecture.md). A suíte de testes aplica o schema uma única
vez por processo contra o PostgreSQL descartável via Alembic. `create_all()`
não substitui esse bootstrap.

### Baseline consolidado

O baseline ativo é `20260803_baseline`; as revisões anteriores foram
arquivadas fora da cadeia ativa. Um banco existente validado no histórico
arquivado deve ser adotado uma única vez por
`.\scripts\adopt_alembic_baseline.ps1 -Confirm`. O procedimento faz backup e
verificação estrutural antes de atualizar somente `alembic_version`, sem DDL
ou mudança de dados. Bancos novos continuam usando `flask db upgrade`.

## Alterações nos critérios de geração

Os parâmetros são normalizados em `app/bets/criteria.py`. Ao mudar um critério,
avalie os consumidores relevantes:

1. normalização e regra de aceitação;
2. geração de apostas simples e múltiplas;
3. relatório combinatório;
4. valores persistidos em configurações;
5. formulário, URL e JavaScript;
6. testes proporcionais ao risco.

Nem toda mudança precisa de cobertura em todos os níveis.

## Decisões sobre limites

Antes de adicionar ou conservar um limite, identifique sua razão:

- validade do domínio;
- proteção de recursos ou segurança;
- custo de processamento, transferência ou armazenamento;
- clareza e capacidade da interface.

Limites externos devem citar a fonte e a data de verificação. Limites internos
devem ficar centralizados, ter mensagem compreensível e possuir testes de
fronteira quando o risco justificar.

## Organização do código

- mantenha cálculos e regras reutilizáveis fora das rotas;
- deixe a transação explícita no caso de uso que grava dados;
- coloque código compartilhado em `app/core` somente quando ele não pertencer a
  uma funcionalidade específica;
- prefira código direto a abstrações sem consumidor concreto;
- mantenha compatibilidade quando houver uso conhecido.

A estrutura atual é um ponto de partida, não um contrato imutável.
