# Contexto tecnico atual

Este arquivo descreve o estado presente do sistema para futuras sessoes do Codex. Nao manter historico aqui; registrar apenas a forma atual da aplicacao, contratos importantes e cuidados para evolucao.

## Estado do produto

- Aplicacao web Flask para importar resultados historicos da Mega Sena, consultar concursos, analisar estatisticas e gerar apostas.
- Versao de referencia atual: `beta_1`.
- Entry point: `run.py`.
- Banco local: `instance/mega_sena.db`; a pasta `instance/` fica fora do Git.
- A aplicacao cria tabelas e configuracoes ausentes na inicializacao com `db.create_all()`, `ensure_default_config()` e `refresh_draw_parameters()`.
- Testes principais ficam em `tests/test_app.py`; comando usual: `py -m pytest`.

## Estrutura

- `app/__init__.py`: factory Flask, configuracao SQLite, filtros Jinja de moeda e inicializacao do banco.
- `app/models.py`: modelos `Draw`, `GeneratedBet` e `Config`.
- `app/routes.py`: rotas web, leitura/persistencia dos parametros de geracao, filtros da tela de apostas e endpoints JSON.
- `app/services.py`: importacao XLSX, estatisticas, combinacoes, filtros, geracao aleatoria segura e fechamentos matematicos.
- `app/templates/`: telas HTML.
- `app/static/style.css`: estilos e tokens visuais.
- `README.md`: instrucoes de execucao e visao geral para usuario.

## Funcionalidades atuais

- Importacao de planilhas `.xlsx` com concursos historicos.
- Dashboard com frequencia, atrasos, pares, trios, soma, paridade, sequencias, faixas e premiacoes.
- Consulta de concursos em `/contests`, com filtros proprios de historico.
- Geracao de apostas em `/bets` com filtros definidos pelo usuario.
- Racional matematico em `/rationale` e `/api/combinations`.
- Preview de concursos historicos que passariam pelos filtros em `/api/draw-filter-preview`.
- Calculo de parametros individuais por percentual alvo em `/api/filter-targets`.
- Fechamento matematico a partir de um conjunto-base de 6 a 15 dezenas.
- Salvamento de apostas em lotes agrupados por `generation_id`.

## Modelos de dados

- `Draw`: concurso historico importado.
  - Guarda concurso, data, seis dezenas, soma, quantidade de pares, maior sequencia consecutiva, ganhadores e valores de premiacao.
  - A propriedade `numbers` retorna as seis dezenas como lista.
- `GeneratedBet`: aposta gerada ou salva.
  - `generation_id` agrupa apostas salvas no mesmo lote.
  - `numbers_csv` guarda as dezenas.
  - `quantity` permite apostas com 6 a 15 numeros.
  - `score` representa diversidade dentro da geracao.
- `Config`: tabela chave/valor para configuracoes padrao da aplicacao.

## Parametros e filtros de geracao

Os filtros validos da geracao sao:

- `consecutive_count`: maior sequencia consecutiva permitida.
- `even_min`: minimo de dezenas pares.
- `even_max`: maximo de dezenas pares.
- `sum_min`: soma minima das dezenas.
- `sum_max`: soma maxima das dezenas.
- `range_min_occupied`: minimo de faixas ocupadas entre 01-10, 11-20, 21-30, 31-40, 41-50 e 51-60.
- `range_max_per_band`: maximo de dezenas permitidas em uma mesma faixa.

A origem dos parametros e controlada em `app/routes.py`:

- Valores padrao vem da tabela `config` por `get_generation_defaults()`.
- Valores atuais podem ficar na sessao `generation_params`.
- Parametros submetidos por GET/POST na tela `/bets` ou `/rationale` sobrepoem os anteriores quando presentes.
- `localStorage` em `bets.html` apenas restaura campos visualmente no navegador; o servidor so usa os valores depois da submissao.

## Gerador

`generate_bets()` em `app/services.py`:

- Usa `secrets.SystemRandom().sample()` para criar candidatos.
- Evita repetir concursos historicos quando `quantity == 6`.
- Aplica somente os filtros recebidos em `filters`.
- Controla diversidade entre apostas da mesma geracao para evitar apostas quase iguais.
- Retorna apostas em memoria com `persist=False`.
- Grava no banco com `persist=True`.

Nao reintroduzir filtros hardcoded dentro do gerador. Se `filters` estiver vazio, a geracao nao deve aplicar restricoes de paridade, soma, sequencia ou faixa.

## Combinacoes e racional

`build_combination_report()` calcula:

- universo total `C(60, 6)`;
- cobertura de uma aposta com `quantity` numeros usando `C(quantity, 6)`;
- filtros ativos em ordem: pares, soma, distribuicao por faixas e maior sequencia consecutiva;
- combinacoes eliminadas e restantes por etapa;
- chance aproximada dentro do universo filtrado.

`_combination_distribution()` precalcula a distribuicao combinatoria de jogos de 6 dezenas por soma, pares, sequencia e faixas.

## Importacao

`import_results_from_xlsx()`:

- Usa `openpyxl.load_workbook(read_only=True, data_only=True)`.
- Corrige dimensoes ruins da planilha com `reset_dimensions()` quando disponivel.
- Reconhece colunas por nomes normalizados.
- Atualiza concursos existentes quando algum campo muda.
- Recalcula soma, pares e maior sequencia consecutiva.
- Retorna `imported`, `updated` e `ignored`.

## Cuidados para futuras alteracoes

- Ao adicionar filtro de geracao, atualizar `GENERATION_FILTER_KEYS`, `_read_generation_state()`, `_active_filters()`, template `bets.html`, `build_combination_report()`, `_passes_generation_filters()` e testes.
- Manter filtros de historico de `/contests` separados dos filtros de geracao.
- Nao recriar migracoes automaticas na inicializacao sem necessidade explicita.
- Evitar refatoracoes amplas; o projeto e pequeno e direto.
- Rodar `py -m pytest` antes de fechar alteracoes relevantes.
