# Arquitetura

## Visão geral

Aplicação Flask monolítica organizada por funcionalidade. A estrutura separa a
adaptação HTTP, os casos de uso e a persistência sem impor camadas que o sistema
ainda não precisa.

```text
navegador
    ↓
app/web
    ↓
app/bets | app/draws | app/settings
    ↓
SQLAlchemy → PostgreSQL
```

`app/core` contém funções compartilhadas de formatação, números e segurança
HTTP. Templates e arquivos estáticos formam a interface, renderizada pelo
servidor.

## Interface: HTMX, não uma API

Toda a interface é HTML montado no servidor. As interações incrementais usam
HTMX: o servidor devolve um fragmento do próprio template, e o navegador o
troca no lugar certo.

Não existe endpoint JSON. Isso é uma decisão, não uma lacuna: um segundo
formato de resposta significaria montar a mesma tela duas vezes — uma em Jinja
e outra em JavaScript — e as duas versões divergem com o tempo. Cada rota que
serve fragmento compartilha a URL da página completa e responde de acordo com o
cabeçalho `HX-Request`, de modo que a navegação sem JavaScript continua sendo
um caminho completo:

| Página | Fragmento devolvido a `HX-Request` |
|---|---|
| `/dashboard` | o próprio conteúdo do dashboard, para trocar o período |
| `/contests` | a tabela de resultados, para filtrar e paginar |
| `/bets` | o resultado da geração |
| `/bets/preview` | a prévia de universo e cobertura, ao lado do formulário |
| `/bets/filter-targets/fragment` | os campos de critério preenchidos por alvo |
| `/settings` | a confirmação da gravação |

Toda resposta desse tipo sai com `Vary: HX-Request`, para que nenhum cache
intermediário sirva um fragmento no lugar do documento inteiro. O helper
`app/web/helpers.py::render_vary` é o único ponto que produz essas respostas.

O JavaScript próprio (`app/static/base.js` e `app/static/bets.js`) cobre apenas
o que HTML e HTMX não resolvem: alternância de tema, menu, confirmação de ação
destrutiva e os campos que ficam somente-leitura no modo fechamento. Ele não
renderiza dado nenhum.

## Inicialização e configuração

`app.create_app()` é a factory da aplicação. Ela:

1. carrega a configuração padrão e as substituições recebidas;
2. exige uma URL PostgreSQL explícita ou `DB_HOST`, `DB_USER`, `DB_NAME` e
   `DB_PASSWORD_FILE`; a aplicação recusa iniciar com qualquer outro dialeto;
3. inicializa SQLAlchemy e Flask-Migrate;
4. registra o blueprint web e os filtros Jinja.

`create_app()` nunca aplica migrações nem grava dados: nenhuma consulta ao banco
acontece durante a construção da aplicação. Isso é deliberado — `flask db
upgrade` precisa conseguir carregar a aplicação (via `run.py`) só para descobrir
a configuração do banco, antes de o schema existir.

Aplicar migrações é uma etapa controlada e separada, executada antes de o
servidor subir:

```text
flask --app run.py db upgrade
```

Em Docker, `docker-entrypoint.sh` faz isso a cada início de contêiner
(idempotente) antes de `exec` no processo do servidor. Fora do Docker, rode o
comando manualmente após qualquer alteração de schema.

O Compose monta `postgres_password` e `secret_key` como Docker secrets. A
fábrica lê a senha pelo caminho em `DB_PASSWORD_FILE` para construir a URL do
PostgreSQL, e lê a chave pelo caminho em `SECRET_KEY_FILE`. Nenhum dos dois
valores compõe o ambiente do contêiner. `DATABASE_URL` e `SECRET_KEY` diretos
continuam aceitos somente para execução manual compatível e injeção de teste;
não são o contrato do Compose.

Não há etapa de seed. A tela de Configurações lê os valores padrão de geração e
da fonte da planilha em `app/settings/service.py::DEFAULT_CONFIG` quando a linha
correspondente não existe no banco; a primeira gravação do usuário é que cria as
linhas. Um banco recém-migrado é legitimamente vazio e a aplicação funciona assim.

## Módulos

### `app/web`

Recebe requisições, interpreta formulários e parâmetros, chama os serviços e
monta a resposta — página inteira ou fragmento. As rotas estão agrupadas em
login/autenticação, dashboard, concursos, apostas, configurações e usuários.
`app/web/auth.py` cuida de login/logout; `_require_login` (`app/__init__.py`)
nega por padrão toda requisição sem sessão, com `PUBLIC_ENDPOINTS` como a
lista curta e explícita do que fica de fora.

### `app/bets`

- `criteria.py`: normalização e avaliação dos critérios de geração;
- `service.py`: geração, fechamento, gravação e consulta de apostas;
- `combinatorics.py`: universo de resultados, filtros e cobertura.

`GenerationCriteria` é a representação comum dos parâmetros usados pela
interface, pelos serviços e pelo relatório combinatório.

Gerar e gravar são operações separadas. `generate_bets` produz candidatas em
memória e não toca o banco; as apostas só chegam ao PostgreSQL por
`save_generated_bets` ou `save_closure_bets`, depois da confirmação na tela.
Cada lote recebe seu identificador de uma sequence do próprio banco, que é o
que impede duas gravações simultâneas de compartilharem um número de geração.

### `app/draws`

- `importing.py`: validação e importação transacional de planilhas;
- `service.py`: consulta paginada dos concursos;
- `statistics.py`: agregações do dashboard.

`build_stats` calcula apenas o que o dashboard exibe. Ao acrescentar um
indicador, acrescente também quem o mostra — uma agregação sem leitor custa
tempo em toda carga da página e envelhece sem que nada falhe.

### `app/settings`

Lê e grava as preferências da tela de apostas e executa a limpeza de concursos
e apostas solicitada pelo usuário.

### `app/accounts`

Cria usuários, redefine senhas e ativa/desativa contas — usado pela tela
`/usuarios` (`app/web/users.py`) e pelo comando `flask criar-usuario`
(`app/cli.py`), que continua existindo para provisionar o primeiro acesso sem
navegador. `MIN_PASSWORD_LENGTH` é o único ponto de política de senha; os dois
consumidores importam a constante em vez de repeti-la. `set_active` recusa
desativar o último usuário ativo, e a rota recusa que alguém desative a
própria conta — nenhuma outra ordem além dessas duas existe hoje.

### Persistência

`app/models.py` define:

- `Draw`, para concursos e seus valores derivados;
- `GeneratedBet`, para apostas agrupadas por geração;
- `Config`, para preferências persistidas.

As colunas derivadas de `Draw` (`total_sum`, `even_count`, `consecutive_count`)
são protegidas por CHECK constraints que as comparam com as próprias dezenas.
A regra vive no banco, e não só no Python, porque uma linha inconsistente faria
toda estatística derivada mentir sem que nada falhasse.

Alterações de schema são feitas em revisões de `migrations/versions/`, aplicadas
por `flask db upgrade`. Backups são uma responsabilidade operacional separada
(`scripts/backup_postgres.ps1`).

## Segurança e implantação

O escopo padrão é local:

- autenticação é obrigatória: `_require_login` nega por padrão, com
  `PUBLIC_ENDPOINTS` como lista curta e explícita do que é público (login e
  estáticos) — mas não há dono de dado, qualquer usuário autenticado vê e
  altera o acervo inteiro;
- hosts aceitos são `localhost`, `127.0.0.1` e `[::1]`;
- operações de escrita exigem token CSRF;
- as respostas recebem CSP e outros cabeçalhos defensivos;
- cookies de sessão usam `HttpOnly` e `SameSite=Lax`.

Os arquivos de segredo locais ficam em `.secrets/`, ignorados pelo Git. O
script `scripts/provision_secrets.ps1` cria-os a partir de valores legados do
`.env.docker` quando existirem, ou gera valores aleatórios novos, sem imprimi-los.

Cabeçalhos de cliente como `HX-Request` são sinal de negociação de apresentação,
nunca prova de autorização ou origem confiável.

A imagem roda sob gunicorn, com usuário não-root e só recebe os arquivos
necessários para servir a aplicação; testes, requisitos de desenvolvimento,
segredos e certificados locais não entram no estágio `runtime`. PostgreSQL roda
como `postgres`, com filesystem raiz somente leitura, capabilities removidas e
diretórios transitórios em `tmpfs`; o volume de dados permanece gravável. O
Compose padrão usa somente `compose.yaml`, sem bind mount e com limites de 1
vCPU para PostgreSQL e 2 vCPU para a aplicação. Desenvolvimento com código
montado exige incluir explicitamente `compose.dev.yaml` junto do arquivo base.

Esse conjunto não substitui TLS nem proxy reverso. Qualquer exposição fora de
`localhost` exige chave de sessão estável, revisão de `TRUSTED_HOSTS`, HTTPS e
uma estratégia de implantação apropriada. No VPS, a lista de hosts, a
confiança nos cabeçalhos do Nginx e os cookies Secure são configurados por
`MEGA_SENA_TRUSTED_HOSTS`, `MEGA_SENA_TRUST_PROXY_HEADERS` e
`MEGA_SENA_FORCE_HTTPS`; veja `docs/deployment-vps.md`.

## Critérios para evolução

- regras de negócio reutilizáveis devem ser testáveis sem uma requisição HTTP;
- transações devem abranger o caso de uso completo que altera dados;
- mudanças persistentes devem ter uma nova revisão do Alembic;
- limites internos devem ter justificativa de domínio, segurança, desempenho ou
  experiência do usuário;
- compatibilidade deve ser mantida quando existe um consumidor conhecido — e
  só enquanto ele existir;
- novas abstrações devem reduzir complexidade concreta do código atual.
