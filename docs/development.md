# Desenvolvimento

## Ambientes

O projeto pode ser desenvolvido no contêiner ou em uma instalação Python local.
Use o ambiente que melhor atende à alteração; o CI continua sendo a referência
comum.

### Docker e Dev Container

```powershell
Copy-Item .env.docker.example .env.docker
.\scripts\export_local_ca.ps1
docker compose --env-file .env.docker up --build -d
```

A aplicação fica em <http://127.0.0.1:5001>. No VS Code, **Dev Containers:
Reopen in Container** usa o mesmo contêiner `app`.

### Python local

PostgreSQL é o único backend suportado; use o serviço do Docker Compose
(`127.0.0.1:5433` por padrão) ou uma instalação local.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:SECRET_KEY = "chave-de-desenvolvimento"
$env:DATABASE_URL = "postgresql+psycopg://mega_sena:mega_sena_dev_local@127.0.0.1:5433/mega_sena"
python -m flask --app run.py db upgrade
python -m flask --app run.py seed-defaults
python run.py
```

A aplicação publica em <http://127.0.0.1:5000>. `db upgrade` e `seed-defaults`
são comandos explícitos: `create_app()` não migra nem grava dados por conta
própria (veja [Arquitetura](architecture.md)); rode-os de novo depois de
qualquer alteração de schema.

## Qualidade

A suíte de testes exige um PostgreSQL descartável (`TEST_DATABASE_URL`, ou
`DATABASE_URL` como alternativa); nenhum teste usa SQLite para simular
persistência. Testes puros de `tests/unit/` não tocam o banco.

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://mega_sena:mega_sena_dev_local@127.0.0.1:5433/mega_sena_test"
python -m ruff check app migrations scripts tests run.py
python -m pytest -q
```

No Docker, aponte para o banco descartável exposto pelo serviço `postgres`:

```powershell
docker compose --env-file .env.docker run --rm --no-deps `
  -e TEST_DATABASE_URL=postgresql+psycopg://mega_sena:mega_sena_dev_local@postgres:5432/mega_sena_test `
  app python -m pytest -q
docker compose --env-file .env.docker run --rm --no-deps app python -m ruff check app migrations scripts tests run.py
```

A auditoria de dependências de runtime é:

```powershell
python scripts/audit_dependencies.py
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

Depois de alterar um modelo:

```powershell
flask --app run.py db migrate -m "descrição"
flask --app run.py db upgrade
python -m pytest -q tests/integration/test_migrations.py
```

No contêiner em execução:

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
vez por processo contra o PostgreSQL descartável; os `db.create_all()` que
aparecem em testes individuais são idempotentes e servem como salvaguarda, não
como substituto das migrações.

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
