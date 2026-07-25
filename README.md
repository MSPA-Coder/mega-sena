# Mega Sena AI

Aplicação web local para importar resultados da Mega-Sena, explorar estatísticas
e montar apostas com critérios configuráveis. O projeto não prevê sorteios nem
promete vantagem estatística: frequências históricas e filtros servem para
análise e organização das combinações.

## Principais recursos

- importação de resultados por planilha `.xlsx`;
- dashboard com frequência, soma, paridade, sequências e premiações;
- consulta e filtragem dos concursos importados;
- geração aleatória de apostas com critérios opcionais;
- fechamento completo a partir de um conjunto de dezenas;
- relatório do universo combinatório e da cobertura das apostas;
- gravação e consulta dos lotes gerados;
- configuração de valores padrão pela própria interface.

## Desenvolvimento com VS Code, Docker e PostgreSQL

Este é o ambiente recomendado para executar e desenvolver o projeto. Ele não
requer `.venv`, Python, Flask ou SQLAlchemy instalados diretamente no Windows:
as dependências Python ficam dentro do contêiner `app`.

O ambiente usa dois contêineres:

- `app`: aplicação Flask e ferramentas de desenvolvimento;
- `postgres`: PostgreSQL 17 com volume persistente.

As portas são publicadas somente no loopback do Windows. Para iniciar:

```powershell
Copy-Item .env.docker.example .env.docker
.\scripts\export_local_ca.ps1
docker compose --env-file .env.docker up --build -d
```

A aplicação fica em `http://127.0.0.1:5001` e o PostgreSQL em
`127.0.0.1:5433`. O VS Code também pode usar **Dev Containers: Reopen in
Container**. Nesse modo, o interpretador selecionado é
`/usr/local/bin/python`, fornecido pela imagem Docker.

Para migrar os dados preservados em `instance/mega_sena.db`:

```powershell
docker compose --env-file .env.docker --profile tools run --rm migrate
docker compose --env-file .env.docker exec app python -m scripts.verify_postgres
```

O migrador substitui apenas os dados das tabelas da aplicação no PostgreSQL,
preserva os IDs, ajusta as sequências e grava a conferência em
`migration_report.json`. O SQLite original permanece intacto como cópia de
segurança.

Para executar a suíte Linux isolada com SQLite temporário:

```powershell
docker compose --env-file .env.docker run --rm --no-deps -e DATABASE_URL= app python -m pytest -q
```

Para parar sem remover os dados:

```powershell
docker compose --env-file .env.docker down
```

Não use `down -v` sem intenção explícita, pois essa opção remove o volume do
PostgreSQL.

Para criar um backup em formato próprio do PostgreSQL:

```powershell
.\scripts\backup_postgres.ps1
```

Os arquivos `.dump` são gravados em `instance/backups`.

As ferramentas de teste e lint já são instaladas na imagem a partir de
`requirements-dev.txt`.

## Fluxo de uso

1. Em **Concursos**, importe uma planilha `.xlsx` com os resultados.
2. Consulte o dashboard e a lista de concursos.
3. Em **Apostas**, ajuste os critérios ou informe as dezenas de um fechamento.
4. Revise as combinações geradas e grave apenas os lotes que quiser conservar.
5. Em **Configurações**, altere os valores iniciais usados pela tela de apostas.

## Escopo atual

O sistema foi projetado para uso local e individual, sem cadastro de usuários.
A persistência é PostgreSQL, executado em contêiner conforme descrito acima; o
SQLite permanece apenas como banco efêmero da suíte de testes isolada
(`-e DATABASE_URL=`), sem infraestrutura externa. A interface aceita apostas e
fechamentos de 6 a 15 dezenas; esse é um limite operacional do aplicativo, não
uma descrição das regras oficiais da Mega-Sena. A importação aceita somente
`.xlsx`.

Se a aplicação for exposta fora da máquina local, use um servidor WSGI adequado
e defina uma `SECRET_KEY` estável e secreta. O servidor embutido de `run.py` é
destinado ao uso local.

## Documentação

- [Arquitetura](docs/architecture.md): organização e responsabilidades atuais.
- [Regras funcionais](docs/business-rules.md): comportamento observado pelo usuário.
- [Desenvolvimento](docs/development.md): ambiente, testes, migrações e critérios de manutenção.

## Estrutura

```text
app/
|-- bets/          # critérios, geração e cálculos combinatórios
|-- core/          # utilitários compartilhados e segurança HTTP
|-- draws/         # importação, consultas e estatísticas
|-- settings/      # configurações e manutenção dos dados
|-- web/           # rotas e adaptação HTTP
|-- static/        # JavaScript e CSS
|-- templates/     # páginas e componentes Jinja
|-- models.py      # modelos persistidos
`-- schema.py      # aplica as migrações do Alembic na inicialização
docs/
migrations/
scripts/
tests/
```

## Verificação

```powershell
docker compose --env-file .env.docker run --rm --no-deps -e DATABASE_URL= app python -m pytest -q
docker compose --env-file .env.docker run --rm --no-deps app python -m ruff check app migrations scripts tests run.py
docker compose --env-file .env.docker run --rm --no-deps app python scripts/audit_dependencies.py
```

O CI executa Ruff e pytest com Python 3.11 e 3.13. A auditoria de dependências
é executada no acionamento manual do workflow e na rotina semanal.
