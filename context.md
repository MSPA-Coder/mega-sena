# Contexto Para IAs

Este arquivo e o handoff tecnico do projeto. Ele descreve o estado atual, os
contratos de codigo e os pontos que uma IA deve preservar ao modificar o
sistema. Nao manter historico aqui.

## Leitura Recomendada

Para entender uma tarefa rapidamente:

1. Leia `README.md` para mapa operacional.
2. Leia este arquivo para invariantes e pontos de extensao.
3. Leia `tests/test_app.py` perto dos testes do comportamento que sera tocado.
4. Leia o modulo alvo em `app/`.

## Arquitetura Atual

Aplicacao Flask com renderizacao server-side, SQLite local e SQLAlchemy.

- Entry point: `run.py`.
- Factory: `create_app()` em `app/__init__.py`.
- Blueprint principal: `bp = Blueprint("web", __name__)` em `app/routes.py`.
- Banco local: `instance/mega_sena.db`.
- Dependencias de runtime: `Flask`, `Flask-SQLAlchemy`, `openpyxl` e
  `defusedxml`.
- Dependencias de desenvolvimento: `pytest`, `Ruff` e `pip-audit`.
- Testes: `tests/test_app.py`.

Na inicializacao, `create_app()`:

- configura logging se ainda nao houver handler externo;
- cria `instance/` se necessario;
- le `SECRET_KEY` do ambiente ou gera uma chave temporaria;
- configura `SQLALCHEMY_DATABASE_URI` para SQLite local;
- limita upload a 10 MB;
- registra filtros Jinja `brl` e `brl0`;
- registra o blueprint;
- injeta versao de asset baseada no `mtime` de `style.css`;
- cria tabelas com `db.create_all()`;
- garante configuracoes padrao;
- recalcula campos derivados dos concursos existentes apenas quando a versao
  interna desse calculo muda.

`create_app(config=None)` aceita overrides de configuracao, inclusive banco em
memoria para testes, sem alterar os defaults de execucao local.
O default de `TRUSTED_HOSTS` aceita somente `localhost`, `127.0.0.1` e `[::1]` para
reduzir risco de Host header/DNS rebinding no uso local.

## Modelos

`Draw` representa um concurso importado:

- `contest` e unico e indexado.
- `n1` a `n6` guardam as dezenas ordenadas.
- `total_sum`, `even_count` e `consecutive_count` sao derivados.
- campos de premiacao ficam em centavos.
- `numbers` retorna `[n1, n2, n3, n4, n5, n6]`.

`GeneratedBet` representa aposta salva ou criada em memoria:

- `generation_id` agrupa apostas gravadas no mesmo lote.
- `numbers_csv` guarda dezenas separadas por virgula.
- `quantity` aceita 6 a 15 dezenas.
- `score` representa diversidade dentro da geracao.
- `numbers` converte `numbers_csv` para lista de inteiros.

`Config` e uma tabela chave/valor:

- usada para defaults de geracao;
- atualizada por `/settings`;
- normalizada por `get_config_values()` e `update_config_values()`.

## Configuracoes e Filtros

Chaves atuais de `DEFAULT_CONFIG`:

- `bet_quantity`
- `generation_amount`
- `consecutive_count`
- `even_min`
- `even_max`
- `sum_min`
- `sum_max`
- `range_min_occupied`
- `range_max_per_band`

Filtros de geracao em `GENERATION_FILTER_KEYS`:

- `consecutive_count`: maior sequencia consecutiva permitida.
- `even_min`: minimo de dezenas pares.
- `even_max`: maximo de dezenas pares.
- `sum_min`: soma minima.
- `sum_max`: soma maxima.
- `range_min_occupied`: minimo de faixas ocupadas entre 01-10, 11-20, 21-30,
  31-40, 41-50 e 51-60.
- `range_max_per_band`: maximo de dezenas em uma mesma faixa.

Limites sao centralizados em `CONFIG_LIMITS`. `even_min > even_max` e ajustado
fazendo `even_max = even_min`; `sum_min > sum_max` troca os valores.

## Estado da Geracao

Fluxo em `app/routes.py`:

- `get_generation_defaults()` le valores de `Config`.
- `_read_generation_state()` combina defaults, sessao `generation_params` e
  GET/POST.
- `_active_filters()` remove filtros `None`.
- `_persist_generation_state()` salva filtros e `amount` na sessao quando uma
  submissao contem parametros de geracao.
- `/bets/clear` limpa apenas filtros da sessao e sinaliza a UI para limpar o
  `localStorage`.

Observacao importante: `quantity` aparece em alguns formularios/URLs, mas a
leitura server-side atual define a quantidade a partir de `Config.bet_quantity`.
Antes de mudar isso, revise testes que esperam esse comportamento.

## Importacao XLSX

Funcao principal: `import_results_from_xlsx(source)`.

Comportamento:

- usa `openpyxl.load_workbook(read_only=True, data_only=True, keep_links=False)`;
- le a primeira planilha;
- chama `reset_dimensions()` quando disponivel;
- reconhece colunas por nomes normalizados;
- exige `contest` e seis dezenas validas entre 1 e 60;
- ordena dezenas antes de salvar;
- ignora concursos duplicados dentro do mesmo arquivo;
- atualiza concurso existente se algum campo mudou;
- calcula `total_sum`, `even_count` e `consecutive_count`;
- converte valores monetarios para centavos;
- limita a 10.000 linhas de dados;
- valida o ZIP antes do `openpyxl`, com limites para quantidade de partes,
  tamanho descompactado e taxa de compressao;
- usa `defusedxml`, recomendado pelo proprio `openpyxl` para endurecer o parser
  contra ataques XML;
- rejeita concursos fracionarios, nulos ou negativos e normaliza ganhadores e
  valores monetarios nao finitos/negativos;
- retorna `{"imported": int, "updated": int, "ignored": int}`.

O upload web aceita somente extensao `.xlsx` e nao persiste o arquivo enviado.

## Estatisticas e Dashboard

Funcoes principais:

- `build_stats(count=None)`: payload server-side completo do dashboard.
- `build_recent_frequency(count)`: payload antigo/especifico de frequencia.
- `_build_sum_histogram()`: buckets de soma.

`count=None` significa historico completo. Quando `count` vem por endpoint, os
valores sao limitados entre 10 e 10.000.

`/api/dashboard-stats` retorna todos os campos usados para atualizar dashboard:

- totais de concursos;
- concursos com/sem acertadores;
- `prize_cards`;
- distribuicoes de pares, sequencia e faixas;
- mais/menos frequentes;
- frequencia por dezena;
- histograma de soma.

## Geracao de Apostas

Funcao principal: `generate_bets(quantity, amount, persist=True, filters=None)`.

Contratos:

- `quantity` e limitado a 6..15.
- `amount` e limitado a 1..100.
- usa `secrets.SystemRandom().sample(range(1, 61), quantity)`.
- se `quantity == 6`, evita repetir concurso historico ja importado.
- filtros sao opcionais; filtro ausente nao restringe.
- se `quantity > 6`, cada subconjunto interno de 6 dezenas precisa passar pelos
  filtros. Assim todas as `C(quantity, 6)` combinacoes contabilizadas no
  racional pertencem ao universo filtrado.
- diversidade evita apostas quase iguais no mesmo lote.
- maximo de tentativas: `amount * 2000`.
- com `persist=False`, retorna objetos em memoria sem gravar.
- com `persist=True`, aloca um `generation_id`, grava e comita o lote inteiro.

Nao adicionar heuristicas silenciosas dentro de `generate_bets()`. Todo criterio
deve passar por `filters` ou por uma nova regra explicitamente testada.

## Fechamento Matematico

Funcao principal: `generate_closure_bets(numbers)`.

Contratos:

- aceita 6 a 15 dezenas distintas;
- rejeita dezenas fora de 1..60;
- retorna todas as combinacoes `C(n, 6)`;
- sempre gera apostas de 6 dezenas;
- nao aplica filtros de geracao.

Nas rotas, `_apply_closure_mode()` detecta `closure_numbers` valido, zera
filtros e troca `selected_amount` para `math.comb(base_count, 6)`.

## Combinatoria e Racional

Funcoes principais:

- `_combination_distribution()`: distribuicao combinatoria cacheada para todos
  os jogos de 6 dezenas.
- `count_possible_draw_combinations(...)`: conta combinacoes que passam pelos
  filtros.
- `build_combination_report(quantity=6, filters=None)`: gera etapas exibidas no
  resumo e em `/rationale`.

Ordem dos filtros no racional:

1. Quantidade de pares.
2. Soma.
3. Distribuicao por faixas.
4. Maior sequencia consecutiva.

O universo inicial e `C(60, 6) = 50.063.860`. A cobertura de uma aposta com
`quantity` dezenas e `C(quantity, 6)`.

## Rotas e Segurança

`app/routes.py` aplica:

- CSRF por sessao em POST/PUT/PATCH/DELETE;
- helper `csrf_token()` injetado nos templates;
- `Content-Security-Policy` com nonce aleatorio por requisicao para scripts
  inline, sem `script-src 'unsafe-inline'`;
- `X-Content-Type-Options: nosniff`;
- `X-Frame-Options: SAMEORIGIN`;
- `Referrer-Policy: same-origin`;
- `Permissions-Policy` bloqueando camera, microfone e geolocalizacao.
- `Cross-Origin-Opener-Policy: same-origin`;
- `X-Permitted-Cross-Domain-Policies: none`.

Qualquer formulario mutante novo precisa incluir `_csrf_token`.

## UI e Templates

Templates atuais:

- `base.html`: layout, navegacao, tema, CSRF helper, menu mobile.
- `dashboard.html`: cards, distribuicoes, graficos e fetch do periodo.
- `bets.html`: formulario de geracao, preview, racional resumido, fechamento,
  historico de geracoes e salvamento.
- `contests.html`: importacao XLSX e tabela paginada.
- `rationale.html`: explicacao combinatoria.
- `settings.html`: defaults de geracao e reset da base.

`bets.html` usa `localStorage` com chave `megaSenaGenerationParams`. Isso e
apenas conveniencia de UI; nao e fonte de verdade para o servidor.

## Checklist Para Adicionar Novo Filtro de Geracao

Atualize, no minimo:

- `DEFAULT_CONFIG` e `CONFIG_LIMITS` em `app/services.py`;
- `GENERATION_FILTER_KEYS` em `app/services.py` e `app/routes.py`;
- `_normalize_config_values()`;
- `_read_generation_state()`;
- `_passes_generation_filters()`;
- `count_possible_draw_combinations()` se afetar o racional combinatorio;
- `build_combination_report()`;
- `count_draws_matching_filters()` se precisar de preview historico;
- `settings.html`;
- `bets.html` e o JavaScript de preview;
- testes em `tests/test_app.py`.

## Testes e Validacao

Comandos padrao:

```powershell
python -m pytest
python -m ruff check app scripts tests run.py
python scripts/audit_dependencies.py
```

Ao mexer em rotas, templates ou CSS, rode a suite completa porque muitos testes
validam HTML renderizado e seletores usados por JavaScript.

## Arquivos Locais e Ignorados

Arquivos/diretorios ignorados relevantes:

- `.venv/`
- `.pytest_cache/`
- `.idea/`
- `dist/`
- `instance/`
- `*.xls`
- `*.xlsx`
- bancos SQLite locais

Nao versionar dados reais de loteria importados, bancos locais, ambientes
virtuais ou caches.
