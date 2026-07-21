# Arquitetura

## Visao geral

O projeto e um monolito modular Flask organizado por funcionalidade. A direcao
esperada das dependencias e:

```text
web -> servicos da funcionalidade -> modelos/extensoes
             |
             `-> core
```

A camada web interpreta HTTP e renderiza respostas. Os pacotes funcionais
implementam casos de uso e consultas. `core` contem apenas infraestrutura
transversal e funcoes puras.

## Pacotes

### `app/__init__.py`

Implementa o Application Factory Pattern. `create_app()` configura a aplicacao,
inicializa extensoes, registra o blueprint, configura SQLite e executa o
bootstrap controlado do banco.

### `app/extensions.py`

Declara `db` e `migrate` sem instancia de aplicacao. `app.__init__` continua
reexportando `db` para compatibilidade com consumidores existentes.

### `app/core/`

- `security.py`: token CSRF, validacao das requisicoes mutantes e headers.
- `formatting.py`: formatacao numerica e monetaria para apresentacao.
- `numbers.py`: parsing numerico e metricas puras das dezenas.

O pacote nao acessa Flask-SQLAlchemy nem conhece rotas.

### `app/bets/`

- `criteria.py`: `GenerationCriteria`, Value Object imutavel e politica unica
  para limites, normalizacao e avaliacao de filtros.
- `service.py`: geracao, fechamento, persistencia e consulta de lotes.
- `combinatorics.py`: distribuicao do universo de jogos, cobertura e alvos.

`GenerationParams` permanece como alias temporario de `GenerationCriteria` em
`app/generation_params.py`. Novos codigos devem importar `GenerationCriteria`
do modulo proprietario.

### `app/draws/`

- `importing.py`: adaptador XLSX e persistencia transacional dos concursos.
- `statistics.py`: agregacoes usadas pelo dashboard.
- `service.py`: consultas e DTOs usados pela camada web.

### `app/settings/`

`service.py` gerencia defaults, configuracoes persistidas e manutencao local.
A transacao de reset pertence a esse servico, nao a uma rota.

### `app/web/`

Todos os modulos compartilham o blueprint `web`, preservando endpoints e URLs:

- `bets.py`
- `contests.py`
- `dashboard.py`
- `settings.py`

As rotas nao importam modelos nem a sessao SQLAlchemy. `app/routes.py` existe
somente como compatibilidade para a antiga localizacao do blueprint.

### Persistencia

`models.py` centraliza os tres modelos SQLAlchemy porque o volume atual nao
justifica repositories genericos ou modelos separados por pacote. `schema.py`
coordena backup, validacao de bancos legados e Alembic. As revisoes permanecem
em `migrations/`, conforme a convencao da ferramenta.

## Interface

`templates/` agrupa paginas por funcionalidade e componentes reutilizaveis em
`templates/components/`. `static/style.css` e um manifesto de CSS; as regras
ficam em `static/css/`, separadas entre tokens, base, componentes, paginas e
responsividade. JavaScript permanece separado por pagina.

## Patterns usados

- Application Factory para composicao da aplicacao.
- Blueprint compartilhado para modularizacao HTTP com endpoints estaveis.
- Service Layer para casos de uso e fronteira de transacao.
- Value Object/Policy em `GenerationCriteria`.
- Adapter na leitura de XLSX.
- DTO em `ContestSearchResult` para impedir acesso ORM pela camada web.

Repository Pattern, Unit of Work customizado, microservicos e hierarquias de
classes abstratas nao sao necessarios no porte atual. Devem ser introduzidos
somente diante de uma necessidade concreta.
