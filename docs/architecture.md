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
2. escolhe o banco por `DATABASE_URL`, usando SQLite local quando a variável
   não está definida;
3. inicializa SQLAlchemy e Flask-Migrate;
4. registra o blueprint web e os filtros Jinja;
5. aplica as migrações pendentes;
6. garante as configurações iniciais e os parâmetros derivados dos concursos.

O Docker Compose define `DATABASE_URL` para PostgreSQL. SQLite e PostgreSQL usam
o mesmo conjunto de modelos e revisões do Alembic; o modo batch é habilitado
somente para migrações SQLite.

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

Alterações de schema são feitas em revisões de `migrations/versions/`. A
aplicação aplica as revisões pendentes ao iniciar; backups continuam sendo uma
responsabilidade operacional separada.

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

Esse conjunto não substitui autenticação, TLS ou um servidor WSGI de produção.
Qualquer exposição em rede exige definir uma `SECRET_KEY` estável, revisar
`TRUSTED_HOSTS`, adicionar controle de acesso e escolher uma estratégia de
implantação apropriada.

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
