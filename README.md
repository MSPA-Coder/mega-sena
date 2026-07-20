# Mega Sena AI

Documentacao curta para humanos e IAs entenderem o estado atual do projeto sem
vasculhar todo o codigo primeiro.

## Resumo do Sistema

Mega Sena AI e uma aplicacao Flask local para importar concursos historicos da
Mega Sena, consultar estatisticas e gerar apostas com filtros configuraveis. O
sistema nao tenta prever sorteios; ele organiza dados, calcula metricas e mostra
cobertura combinatoria.

Fonte de verdade do comportamento:

- `app/__init__.py`: cria a aplicacao, configura SQLite, seguranca basica,
  filtros Jinja e inicializacao do banco.
- `app/models.py`: modelos SQLAlchemy `Draw`, `GeneratedBet` e `Config`.
- `app/services.py`: fachada publica compativel para os servicos de negocio.
- `app/service_modules/`: implementacoes separadas por dominio.
- `app/generation_params.py`: fonte unica dos parametros e limites de geracao.
- `app/routes.py`: rotas Flask, estado por URL/formulario, CSRF e endpoints JSON.
- `app/templates/`: telas renderizadas pelo servidor.
- `app/static/`: CSS e JavaScript modular de base, apostas e dashboard.
- `tests/`: suite de regressao organizada por dominio, com fixtures comuns.
- `pyproject.toml`: configuracao das ferramentas de teste e lint.

## Como Rodar

Requisitos:

- Python 3.11 ou superior.
- `pip`.
- Ambiente virtual recomendado.

Instalacao local:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Para desenvolver e executar todas as verificacoes locais:

```powershell
pip install -r requirements-dev.txt
```

URL padrao:

```text
http://127.0.0.1:5000
```

Para ambiente fora de desenvolvimento, defina `SECRET_KEY` antes de iniciar. Sem
essa variavel, a aplicacao gera uma chave temporaria a cada boot.
Por padrao, apenas os hosts locais `localhost`, `127.0.0.1` e `[::1]` sao aceitos;
uma implantacao com dominio proprio deve sobrescrever `TRUSTED_HOSTS` na factory.

## Banco e Dados Locais

O banco SQLite fica em:

```text
instance/mega_sena.db
```

`instance/` e ignorado pelo Git porque contem dados locais. Na inicializacao, o
app aplica as revisoes de `migrations/` com Flask-Migrate/Alembic. Banco novo e
criado pela migracao inicial. Banco legado compativel e reconhecido somente
depois de um backup consistente pela API do SQLite. Antes de upgrades futuros,
outro backup e criado em `instance/backups/`.

Depois do schema atualizado, o app garante as configuracoes padrao e atualiza
campos derivados quando a versao interna do calculo muda.

## Rotas Principais

- `/`: redireciona para `/dashboard`.
- `/dashboard`: estatisticas dos concursos importados.
- `/bets`: geracao, fechamento matematico, revisao e salvamento de apostas.
- `/bets/clear`: limpa filtros e redireciona para uma URL sem esses parametros.
- `/rationale`: explica o racional combinatorio dos filtros ou fechamento.
- `/contests`: lista concursos, filtros de historico e upload de `.xlsx`.
- `/contests/import`: recebe a planilha de concursos.
- `/settings`: configuracoes padrao e reset da base local.
- `/reset`: apaga concursos e apostas locais.
- `/import`: compatibilidade; redireciona para `/contests`.

Endpoints JSON usados pela UI:

- `/api/dashboard-stats`
- `/api/recent-frequency`
- `/api/draw-filter-preview`
- `/api/filter-targets`
- `/api/combinations`

## Funcionalidades Atuais

- Importacao de planilhas `.xlsx` da Mega Sena pela aba Concursos.
- Atualizacao de concursos ja existentes quando campos importados mudam.
- Dashboard com frequencia, atrasos, pares, trios, soma, paridade, sequencias,
  faixas e premiacoes.
- Filtro global de periodo do dashboard via `/api/dashboard-stats`.
- Consulta paginada de concursos com filtros de historico.
- Geracao de apostas usando `secrets.SystemRandom`.
- Filtros por pares, soma, maior sequencia consecutiva e faixas `01-10` a
  `51-60`.
- Preview de quantos concursos historicos passariam pelos filtros atuais.
- Sugestao de parametros por percentual alvo individual.
- Racional combinatorio com total, eliminadas, restantes e chance aproximada.
- Fechamento matematico a partir de 6 a 15 dezenas-base.
- Salvamento de apostas em lotes por `generation_id`.
- CSRF em metodos mutantes e headers basicos de seguranca.
- Alternancia de tema claro/escuro por cookie.

## Regras Importantes Para IAs

- Nao reintroduza filtros hardcoded em `generate_bets()`. Se `filters` estiver
  vazio, a geracao nao deve filtrar por pares, soma, sequencia ou faixas.
- Os filtros de historico de `/contests` sao diferentes dos filtros de geracao
  de `/bets`.
- A quantidade padrao vem de `Config.bet_quantity`; quando a URL ou formulario
  traz `quantity`, o valor informado faz parte do estado reproduzivel da tela.
- URL e formularios sao a fonte de verdade. Filtros nao sao persistidos na
  sessao nem em `localStorage`, permitindo abas independentes.
- O fechamento matematico nao sorteia candidatas; ele enumera todas as
  combinacoes de 6 dezenas dentro do conjunto-base informado.
- Imports aceitam apenas `.xlsx` no upload e limitam a leitura a 10.000 linhas de
  dados. O arquivo compactado tambem e validado antes da leitura para limitar
  quantidade de partes, tamanho expandido e taxa de compressao.
- Planilhas enviadas nao sao salvas no projeto.
- Em apostas de 7 a 15 dezenas, todos os subconjuntos internos de 6 dezenas
  precisam passar pelos filtros; isso mantem coerente a cobertura `C(n, 6)` do
  racional.
- Apostas salvas sao normalizadas, deduplicadas dentro do lote e limitadas ao
  maior fechamento suportado, `C(15, 6) = 5.005`.
- O app e local/single-user; nao ha autenticacao ou autorizacao de usuarios.

## Testes

Comandos recomendados, depois de instalar `requirements-dev.txt`:

```powershell
python -m pytest
python -m ruff check app migrations scripts tests run.py
python scripts/audit_dependencies.py
```

A suite cobre migracoes e backups, importacao e limites de XLSX, filtros,
combinatoria, endpoints, CSRF/CSP, reset, factory, dashboard, UI e apostas. O
workflow `.github/workflows/ci.yml` executa pytest e Ruff em Python 3.11/3.13;
a auditoria de dependencias e semanal ou manual.

## Estrutura

```text
.
|-- app/
|   |-- __init__.py
|   |-- generation_params.py
|   |-- models.py
|   |-- routes.py
|   |-- schema.py
|   |-- services.py
|   |-- service_modules/
|   |-- static/
|   |   |-- base.js
|   |   |-- bets.js
|   |   |-- dashboard.js
|   |   `-- style.css
|   `-- templates/
|       |-- base.html
|       |-- bets.html
|       |-- contests.html
|       |-- dashboard.html
|       |-- rationale.html
|       `-- settings.html
|-- migrations/
|-- tests/
|   |-- conftest.py
|   |-- support.py
|   `-- test_*.py
|-- .github/workflows/ci.yml
|-- scripts/
|   `-- audit_dependencies.py
|-- context.md
|-- pyproject.toml
|-- requirements.txt
|-- requirements-dev.txt
|-- run.py
`-- README.md
```

## Limites do Produto

A Mega Sena e um sorteio aleatorio. Este sistema nao aumenta a chance real de
acerto alem da cobertura combinatoria das apostas feitas. Use como ferramenta de
analise, simulacao e organizacao.
