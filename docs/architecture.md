# Arquitetura

## Visão geral

O projeto é uma aplicação Flask monolítica organizada por funcionalidade. A
estrutura separa a adaptação HTTP, os casos de uso e a persistência sem impor
camadas que o sistema ainda não precisa.

```text
navegador
    ↓
app/web
    ↓
app/bets | app/draws | app/settings
    ↓
SQLAlchemy
```

`app/core` contém funções compartilhadas de formatação, números e segurança
HTTP. Templates e arquivos estáticos formam a interface renderizada pelo
servidor.

## Inicialização e configuração

`app.create_app()` é a factory da aplicação. Ela:

1. carrega a configuração padrão e as substituições recebidas;
2. exige `DATABASE_URL` apontando para PostgreSQL — a aplicação recusa iniciar
   sem uma URL válida; SQLite não é um backend operacional (a única leitura
   legítima de SQLite no projeto é o script explícito de importação de base
   legada, `scripts/migrate_sqlite_to_postgres.py`, que não passa por esta
   fábrica);
3. inicializa SQLAlchemy e Flask-Migrate;
4. registra o blueprint web, os filtros Jinja e o comando `flask seed-defaults`.

`create_app()` nunca aplica migrações nem grava dados por conta própria —
nenhuma consulta ao banco acontece durante a construção da aplicação. Isso é
deliberado: `flask db upgrade` precisa conseguir carregar a aplicação (via
`run.py`) só para descobrir a configuração do banco, antes de o schema
existir. Migrações e seed de dados são etapas controladas e separadas,
executadas nesta ordem antes de iniciar o servidor:

1. `flask --app run.py db upgrade` — aplica as revisões pendentes do Alembic;
2. `flask --app run.py seed-defaults` — garante configuração padrão e
   parâmetros derivados dos concursos.

Em Docker, `docker-entrypoint.sh` executa essas duas etapas a cada início de
contêiner (idempotentes) antes de `exec` no processo do servidor (gunicorn em
produção, `python run.py` em desenvolvimento). Fora do Docker, rode os dois
comandos manualmente após qualquer alteração de schema.

## Módulos

### `app/web`

Recebe requisições, interpreta formulários e parâmetros, chama os serviços e
monta respostas HTML ou JSON. As rotas estão agrupadas em dashboard, concursos,
apostas e configurações.

### `app/bets`

- `criteria.py`: normalização e avaliação dos critérios de geração;
- `service.py`: geração, fechamento, persistência e consulta de apostas;
- `combinatorics.py`: universo de resultados, filtros e cobertura.

`GenerationCriteria` é a representação comum dos parâmetros usados pela
interface, pelos serviços e pelo relatório combinatório.

### `app/draws`

- `importing.py`: validação e importação transacional de planilhas;
- `service.py`: consulta paginada dos concursos;
- `statistics.py`: agregações do dashboard e parâmetros derivados.

### `app/settings`

Lê e grava as preferências da tela de apostas e executa a limpeza de concursos
e apostas solicitada pelo usuário.

### Persistência

`app/models.py` define:

- `Draw`, para concursos e seus dados calculados;
- `GeneratedBet`, para apostas agrupadas por geração;
- `Config`, para preferências persistidas.

Alterações de schema são feitas em revisões de `migrations/versions/`, aplicadas
por `flask db upgrade` como etapa controlada (nunca automaticamente pela
aplicação — veja "Inicialização e configuração"). Backups continuam sendo uma
responsabilidade operacional separada (`scripts/backup_postgres.ps1`).

## Interface

As páginas Jinja ficam em `app/templates/`. O CSS é composto por tokens,
componentes e estilos de página em `app/static/css/`. O JavaScript fica em
arquivos externos carregados com `defer`; a versão dos assets usa o horário de
modificação dos arquivos para evitar cache desatualizado.

## Segurança e implantação

O escopo padrão é local:

- hosts aceitos são `localhost`, `127.0.0.1` e `[::1]`;
- operações de escrita exigem token CSRF;
- as respostas recebem CSP e outros cabeçalhos defensivos;
- cookies de sessão usam `HttpOnly` e `SameSite=Lax`.

A imagem de produção (`Dockerfile`, estágio `runtime`) roda a aplicação sob
gunicorn (WSGI), com usuário não-root e sem bind mount — imutável entre
implantações. `compose.override.yaml`, mesclado automaticamente em
desenvolvimento, troca para o estágio `dev` (bind mount, servidor de
desenvolvimento do Flask); a imagem de produção é obtida ignorando esse
override (`docker compose -f compose.yaml ...`).

Esse conjunto não substitui autenticação, TLS ou um proxy reverso adequado à
rede em que a aplicação for exposta. Qualquer exposição fora de `localhost`
exige definir uma `SECRET_KEY` estável, revisar `TRUSTED_HOSTS`, adicionar
controle de acesso e escolher uma estratégia de implantação apropriada (TLS
terminado por um proxy reverso, por exemplo).

## Critérios para evolução

- regras de negócio reutilizáveis devem ser testáveis sem uma requisição HTTP;
- transações devem abranger o caso de uso completo que altera dados;
- mudanças persistentes devem ter uma nova revisão do Alembic;
- limites internos devem ter justificativa de domínio, segurança, desempenho ou
  experiência do usuário;
- compatibilidade deve ser mantida quando existe um consumidor conhecido;
- novas abstrações devem reduzir complexidade concreta do código atual.

Esses critérios orientam decisões; não são restrições à reorganização do
projeto.
