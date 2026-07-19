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
- `app/services.py`: importacao XLSX, estatisticas, filtros, combinatoria,
  geracao aleatoria e fechamento matematico.
- `app/routes.py`: rotas Flask, estado de geracao em sessao, CSRF, headers de
  seguranca e endpoints JSON.
- `app/templates/`: telas renderizadas pelo servidor.
- `app/static/style.css`: tema visual, responsividade e estados de UI.
- `tests/test_app.py`: suite de regressao principal.
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
app executa:

- `db.create_all()`;
- `ensure_default_config()`;
- atualizacao versionada dos campos derivados dos concursos, executada apenas
  quando a versao do calculo muda.

Nao ha sistema de migracoes. Alteracoes de schema precisam ser planejadas com
cuidado.

## Rotas Principais

- `/`: redireciona para `/dashboard`.
- `/dashboard`: estatisticas dos concursos importados.
- `/bets`: geracao, fechamento matematico, revisao e salvamento de apostas.
- `/bets/clear`: limpa filtros de geracao da sessao.
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
- A quantidade de dezenas por aposta vem de `Config.bet_quantity` em
  `/settings`; o parametro `quantity` em URLs aparece para retorno de tela, mas
  a leitura server-side atual usa a configuracao como fonte principal.
- `localStorage` em `bets.html` apenas restaura campos visualmente; o servidor
  so considera valores enviados por GET/POST ou salvos na sessao.
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
python -m ruff check app scripts tests run.py
python scripts/audit_dependencies.py
```

A suite cobre importacao e limites de XLSX, filtros, combinatoria, endpoints,
CSRF/CSP, reset, factory, dashboard, UI renderizada e salvamento de apostas.

## Estrutura

```text
.
|-- app/
|   |-- __init__.py
|   |-- models.py
|   |-- routes.py
|   |-- services.py
|   |-- static/
|   |   `-- style.css
|   `-- templates/
|       |-- base.html
|       |-- bets.html
|       |-- contests.html
|       |-- dashboard.html
|       |-- rationale.html
|       `-- settings.html
|-- tests/
|   `-- test_app.py
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
