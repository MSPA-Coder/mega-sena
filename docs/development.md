# Desenvolvimento e validação

## Gate de tipos incremental

O estágio `quality` executa Ruff, `mypy` estrito e pytest. O conjunto pequeno
de fronteiras está em `tool.mypy.files` no `pyproject.toml`; imports mantêm
seus tipos (`follow_imports=silent`), sem esconder erros dos arquivos
selecionados. Amplie por fronteira, com contratos concretos, sem `Any` ou
ignores generalizados. As anotações não substituem validação de payloads,
restrições do PostgreSQL ou os testes de navegador.

## Piloto de navegador isolado

Construa com `docker compose -p mega-browser-tests -f compose.browser.yaml build`.
Com os mesmos `-p` e `-f`, suba `up -d --no-build --wait browser-web`, execute
`run --rm browser-tests` e finalize com `down`. Somente PostgreSQL tmpfs do
piloto é descartado; não há volumes operacionais. `BROWSER_APP_IMAGE` e
`BROWSER_POSTGRES_IMAGE` aceitam candidatos já construídos, sem rebuild.
Fixtures montadas externamente não entram no runtime. Sem portas no host,
contas reais ou dependências externas reais. Falhas deixam PNG em
`.browser-results` (ignorado pelo Git).

O piloto Chromium cobre geração sem escrita, confirmação/replay/evento único,
fechamento, prévia, erro visível preservando formulário e percentual BR/EUA.
O 400 de critério recebe marcador explícito para HTMX; erros genéricos e CSRF
não recebem essa permissão de troca.


O projeto usa Docker para aplicação, PostgreSQL, migrations, lint e testes. No
host são necessários apenas Docker Desktop, Git e um editor; o venv do laço
rápido, descrito no `AGENTS.md`, é opcional.

## Ambiente

```powershell
Copy-Item .env.docker.example .env.docker
.\scripts\provision_secrets.ps1
```

Só exporte uma CA local se o host intercepta HTTPS (por exemplo, por
antivírus ou proxy) e a autoridade raiz dessa inspeção já existe no repositório
de certificados do Windows. O script cria `.certs/` e exporta para
`.certs/local-root-ca.crt`; sem inspeção TLS, não o execute e não crie esse
arquivo. Por padrão ele procura a raiz do Avast; para outro certificado,
informe o padrão do subject:

```powershell
.\scripts\export_local_ca.ps1
# Exemplo para outra CA: .\scripts\export_local_ca.ps1 -SubjectPattern '*Nome da CA*'
```

Depois, suba a pilha de desenvolvimento:

```powershell
docker compose --env-file .env.docker -f compose.yaml -f compose.dev.yaml up --build -d
```

`provision_secrets.ps1` cria, sem exibir os valores,
`.secrets/postgres_password.txt`, `.secrets/secret_key.txt` e
`.secrets/postgres_app_password.txt` (a senha do papel restrito com que o
`app` conecta; o `db-provision` a aplica a cada subida). Se um ambiente
antigo ainda tiver `POSTGRES_PASSWORD` ou `SECRET_KEY` no `.env.docker`, o
script pode migrá-los para arquivos; use `-RemoveLegacyValues` somente depois
de validar a subida. `-Force` troca os segredos e exige tratar a senha do banco
e a invalidação das sessões existentes.

Sem `compose.dev.yaml`, o serviço não monta o código do host e reconstrói com
cache, a partir das imagens-base já baixadas (ver "Imagens-base" abaixo). O
serviço `migrate`
executa `flask --app run.py db upgrade`, com o papel administrativo, antes do
Gunicorn do `app`; `create_app()` apenas monta a
aplicação e não consulta o banco, cria tabelas ou dados iniciais.

## Validação automatizada

O comando oficial executa Ruff e toda a suíte pytest na imagem `quality`:

```powershell
docker compose --env-file .env.docker -f compose.yaml --profile quality run --build --rm quality
```

**`--build` não é opcional.** O serviço `quality` não monta o código do
host: o que ele executa é o que foi copiado para a imagem. `docker compose
run --build` reconstrói a partir do código atual, com cache. Só o
`postgres-teste` monta sem cache, e é isso que o recria vazio a cada execução,
para `app_com_banco` aplicar a cadeia Alembic a um banco vazio.

### Imagens-base

Nem o `quality` nem o deploy buscam imagens-base novas por conta própria: o
Compose não declara `pull`, e as camadas do `apt-get upgrade` ficam em cache
até alguém pedir bases novas. É a mesma regra do servidor, onde um deploy comum
monta sem `--pull` e só `deploy.sh megasena --refresh` busca bases novas. Para
testar bases novas na máquina antes do `--refresh`:

```powershell
docker compose --env-file .env.docker -f compose.yaml --profile quality build --pull --no-cache quality
docker compose --env-file .env.docker -f compose.yaml --profile quality run --build --rm quality
```

A CI semanal faz o mesmo build sem cache e com `--pull`, só como aviso, para
conferir as atualizações do sistema e das dependências.

A suíte protege os contratos HTTP e de segurança — autenticação por padrão,
CSRF, cabeçalhos, proxy, health check, download e limite de login —, a
integridade do grafo Alembic e a configuração de bootstrap. Os testes de
domínio cobrem, sem depender de uma quantidade total fixa de casos:

- normalização e limites dos critérios de geração, aplicação inclusiva dos
  filtros, rejeição de resultados já sorteados, diversidade do lote e ausência
  de persistência antes da confirmação;
- enumeração e validação dos fechamentos, identificação única de lote e
  atomicidade da gravação;
- inclusão, atualização e preservação de campos opcionais na importação de
  concursos, com rollback integral diante de metadado inválido.

Esses testes são contrato de regressão das regras centrais. Uma mudança nessas
regras deve atualizar implementação, testes e `docs/business-rules.md` na mesma
alteração.

O CI valida o Compose, reconstrói sem cache e executa o estágio `quality`. Ele
também audita as dependências Python instaladas com `pip-audit` e a imagem de
runtime com Trivy. O Dependabot acompanha o `uv.lock`, a imagem base e as
GitHub Actions. O CodeQL roda pela configuração padrão do GitHub e é check
obrigatório no `main`, ao lado de `Qualidade`. Não há análise estática de tipos.

## Validação proporcional

Além do comando automatizado:

1. percorra no navegador o fluxo alterado;
2. em mudança de Docker ou dependências, reconstrua a imagem e confira a subida
   e os health checks;
3. em mudança de autenticação, sessão, autorização, CSRF ou proxy, exercite
   também login, logout e uma operação mutante;
4. em mudança persistente, gere e verifique um backup conforme
   `docs/deployment-vps.md`, aplique a cadeia completa em PostgreSQL vazio e
   teste upgrade e downgrade da revisão alterada.

## Schema

O schema evolui somente por novas revisões em `migrations/versions/`. Não
reescreva revisions já aplicáveis, não use `db.create_all()` como bootstrap e
não use `stamp` como substituto de uma migration. Consulte
[`migrations/README`](../migrations/README) para os comandos e a cadeia atual.

A revisão `20261028_0010_bet_confirmation` guarda a identidade dos envios de
apostas. Seu downgrade remove esse histórico: uma confirmação antiga reenviada
depois da remoção deixa de ser reconhecida como repetição. O retorno de código
ou imagem não deve executar esse downgrade automaticamente; antes de remover a
tabela é necessário avaliar o impacto e preservar um backup verificável.
