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
app/bets | app/draws | app/settings | app/accounts
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

Não há API JSON de negócio ou de interface. A exceção é `/health`, endpoint
operacional que responde JSON mínimo para as sondas. Um segundo formato para as
telas significaria montá-las duas vezes — uma em Jinja e outra em JavaScript —
e as versões divergiriam com o tempo. Cada rota que serve fragmento compartilha
a URL da página completa e responde de acordo com o cabeçalho `HX-Request`, de
modo que a navegação sem JavaScript continua sendo um caminho completo:

| Página | Fragmento devolvido a `HX-Request` |
|---|---|
| `/dashboard` | o próprio conteúdo do dashboard, para trocar o período |
| `/contests` | a tabela de resultados, para filtrar e paginar |
| `/bets` | o resultado da geração |
| `/bets/preview` | a prévia de universo e cobertura, ao lado do formulário |
| `/bets/filter-targets/fragment` | os campos de critério preenchidos por alvo |
| `/settings` | a confirmação da gravação |

Toda resposta HTML sai com `Vary: HX-Request`, para que nenhum cache
intermediário sirva um fragmento no lugar do documento inteiro. Essa garantia é
aplicada pelo `sharedauth.security.registrar_cabecalhos`, registrado na factory,
e vale para página inteira e fragmento; `app/web/helpers.py` apenas interpreta o
cabeçalho para escolher qual template renderizar. Respostas estáticas não
recebem esse `Vary`, pois não variam com HTMX.

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

No Compose, o serviço `migrate` faz isso a cada subida (idempotente), com o
papel administrativo `POSTGRES_USER` -- superusuário, dono das tabelas --,
antes de o `app` subir. O `app` conecta com o papel restrito `mega_sena_app`,
que o serviço `db-provision` (`scripts/provision-db-runtime.sh`) cria ou
atualiza a cada subida com DML e uso de sequências, sem DDL; com
`DB_EXIGIR_PAPEL_RESTRITO=1`, `app/papel_do_banco.py` recusa uma conexão
superusuária. O `docker-entrypoint.sh` ainda migra quando
`MEGA_SENA_MIGRAR_NA_SUBIDA` não é `0`, para quem roda a imagem fora do
Compose. Fora do Docker, rode o comando manualmente após qualquer alteração
de schema.

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
`app/web/auth.py` cuida de login/logout; `requer_login`, fornecido pelo
SharedAuth e configurado em `app/__init__.py`, nega por padrão toda requisição
sem sessão, com `PUBLIC_ENDPOINTS` como a lista curta e explícita do que fica
de fora.

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
O serviço também calcula uma impressão digital da confirmação normalizada e
usa um advisory lock transacional: repetir o mesmo envio devolve o lote já
gravado, sem criar apostas duplicadas, inclusive entre workers.

### `app/draws`

- `importing.py`: validação e importação transacional de planilhas;
- `service.py`: consulta paginada dos concursos;
- `statistics.py`: agregações do dashboard.

`build_stats` calcula apenas o que o dashboard exibe. A consulta seleciona
somente as colunas necessárias e agrega em fluxo, em lotes de 1.000 linhas;
assim “Todos” preserva o contrato do histórico completo sem materializar
objetos ORM nem listas proporcionais ao número de concursos. Ao acrescentar um
indicador, acrescente também quem o mostra — uma agregação sem leitor custa
tempo em toda carga da página e envelhece sem que nada falhe.

### `app/settings`

Lê e grava as preferências da tela de apostas e executa a limpeza de concursos
e apostas solicitada pelo usuário. Leituras limitam-se às chaves conhecidas.
Atualizações lockam a tabela `config` dentro da transação antes de ler e
upsertar as linhas, cobrindo inclusive a primeira gravação em banco vazio e
evitando a disputa entre dois salvamentos concorrentes.

### `app/accounts`

Cria usuários, redefine senhas, altera papéis e ativa/desativa contas — usado pela tela
`/usuarios` (`app/web/users.py`) e pelo comando `flask criar-usuario`
(`app/cli.py`), que continua existindo para provisionar o primeiro acesso sem
navegador. A tela é exclusiva de administradores; o primeiro usuário criado
pela CLI recebe esse papel e os demais recebem `operador` por padrão.
`MIN_PASSWORD_LENGTH` é o único ponto de política de senha; os dois
consumidores importam a constante em vez de repeti-la. O serviço serializa as
alterações de conta e impede remover o último administrador, desativar o
último administrador ativo, desativar a própria conta ou deixar zero usuários
ativos.

### Persistência

`app/models.py` define:

- `Draw`, para concursos e seus valores derivados;
- `GeneratedBet`, para apostas agrupadas por geração;
- `Config`, para preferências persistidas;
- `User`, para credenciais e estado de acesso das contas.
- `AuditEvent`, para a trilha persistente de alterações relevantes, separada
  do log técnico e sem segredos.

As colunas derivadas de `Draw` (`total_sum`, `even_count`, `consecutive_count`)
são protegidas por CHECK constraints que as comparam com as próprias dezenas.
A regra vive no banco, e não só no Python, porque uma linha inconsistente faria
toda estatística derivada mentir sem que nada falhasse.

Alterações de schema são feitas em revisões de `migrations/versions/`, aplicadas
por `flask db upgrade`. Backups são uma responsabilidade operacional separada,
do BackupRestore (projeto irmão, fora deste repositório).

## Segurança e implantação

O escopo padrão é local:

- autenticação é obrigatória: `requer_login` nega por padrão, com
  `PUBLIC_ENDPOINTS` como lista curta e explícita do que é público (login,
  health check e estáticos). Não há dono de dado: qualquer usuário autenticado
  vê e altera o acervo inteiro; apenas a gestão de contas é administrativa;
- hosts aceitos são `localhost`, `127.0.0.1` e `[::1]`;
- operações de escrita exigem token CSRF;
- as respostas recebem CSP e outros cabeçalhos defensivos;
- cookies de sessão usam `HttpOnly` e `SameSite=Lax`.

Os arquivos de segredo locais ficam em `.secrets/`, ignorados pelo Git. O
script `scripts/provision_secrets.ps1` cria-os a partir de valores legados do
`.env.docker` quando existirem, ou gera valores aleatórios novos, sem imprimi-los.

O limite de tentativas de login fornecido pelo SharedAuth usa armazenamento em
memória. Cada processo Gunicorn mantém seus próprios contadores: eles não são
compartilhados entre os dois workers atuais ou entre instâncias e são zerados
quando o processo reinicia. Ele é somente uma defesa local por processo, não
uma proteção de produção coordenada.

No VPS, a proteção coordenada fica na borda: a configuração Nginx mantida em
`_manutencao/vps/nginx` aplica uma zona `limit_req` compartilhada ao
`POST /login`. Esse controle é requisito da implantação atual e deve ser
preservado junto com HTTPS e hosts confiáveis. Outra topologia precisa manter
uma proteção equivalente na borda ou adotar armazenamento compartilhado para o
limitador da aplicação; o armazenamento em memória, sozinho, não satisfaz esse
contrato.

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
