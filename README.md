# Mega Sena AI

Aplicação local para importar resultados da Mega-Sena, consultar estatísticas e organizar apostas. Frequências e filtros descrevem somente o histórico importado; não preveem sorteios nem aumentam a probabilidade matemática de uma combinação.

Flask, HTMX e PostgreSQL. A interface é HTML renderizado no servidor.

## Início rápido

```powershell
Copy-Item .env.docker.example .env.docker
.\scripts\provision_secrets.ps1
.\scripts\export_local_ca.ps1
docker compose --env-file .env.docker -f compose.yaml up --build -d
```

A aplicação fica em <http://127.0.0.1:5101>. Os dados ficam no volume `postgres_data`; `docker compose down` não os remove. Use `down -v` apenas para descartar deliberadamente o banco local.

O Compose lê a senha do PostgreSQL e a chave de sessão dos arquivos
`.secrets/postgres_password.txt` e `.secrets/secret_key.txt`, nunca de
variáveis de ambiente do contêiner. O script de provisionamento cria os dois
arquivos sem exibir valores; quando houver `POSTGRES_PASSWORD` ou `SECRET_KEY`
em um `.env.docker` antigo, ele os migra para os arquivos. Depois de confirmar
a subida, use `-RemoveLegacyValues` para remover esses valores legados do
arquivo de ambiente. Arquivos existentes são preservados, salvo `-Force`, que
é uma rotação deliberada.

O comando padrão usa a imagem imutável. Para editar código com bind mount,
inclua explicitamente o arquivo de desenvolvimento:

```powershell
docker compose --env-file .env.docker -f compose.yaml -f compose.dev.yaml up --build -d
```

Ao iniciar, o contêiner aplica a baseline de schema com `flask db upgrade`. Um banco novo não precisa de seed: as configurações usam valores padrão até a primeira gravação.

## Produção

O sistema roda em um VPS Oracle (Ubuntu 24.04), publicado pelo Nginx com
certificado Let's Encrypt em <https://megasena-mspa.duckdns.org>. O contêiner
escuta apenas em `127.0.0.1:5101`; só 80 e 443 ficam abertos na internet.

O fluxo de mudança tem um sentido único: **máquina de desenvolvimento → GitHub →
VPS**. O código no servidor é um espelho do `main` e nunca a origem de uma
alteração; a implantação é feita por `~/deploy.sh megasena`, que recusa rodar se
encontrar alteração não commitada no servidor. O repositório é privado e o VPS o
lê por uma *deploy key* somente-leitura.

Detalhes de instalação, atualização e rollback estão em
[Implantação no VPS](docs/deployment-vps.md).

## Uso

1. Importe a planilha em **Concursos**.
2. Consulte o dashboard ou filtre os concursos.
3. Em **Apostas**, gere jogos ou informe dezenas para um fechamento.
4. Revise e grave somente os lotes desejados.
5. Ajuste os valores padrão em **Configurações**.

Para criar um backup antes de mudanças de schema ou manutenção:

```powershell
.\scripts\backup_postgres.ps1
```

Os arquivos são gravados em `instance/backups/`.

## Acesso

A aplicação exige login. Não há tela pública de cadastro: o primeiro usuário é
criado pela linha de comando, dentro do contêiner.

```powershell
docker compose --env-file .env.docker -f compose.yaml exec app flask --app run.py criar-usuario
```

O comando pergunta usuário e senha (mínimo de 2 caracteres) sem ecoar a senha.
Rodar de novo com um usuário existente redefine a senha dele. Usuários
seguintes podem ser criados pela própria interface, em **Usuários**
(`/usuarios`) — qualquer conta autenticada pode criar, redefinir senha e
ativar/desativar outras contas por lá; a linha de comando continua útil só
para o primeiro acesso, antes de existir sessão.

Login não separa dados: qualquer usuário autenticado vê e altera todos os
concursos, apostas e configurações.

## Manutenção

O projeto é de uso individual. Não mantém uma suíte ampla de regressão,
cobertura, análise estática de tipos ou `pip-audit` dentro da imagem. Mantém
Ruff e a suíte mínima de segurança e fumaça, que rodam juntos no estágio
`quality` da imagem:

```powershell
docker compose --env-file .env.docker -f compose.yaml --profile quality run --rm quality
```

Para alterações relevantes, valide o fluxo afetado no navegador e, quando houver mudança no banco, faça backup e confira a criação de um PostgreSQL vazio pela baseline.

O workflow de CI executa essa validação enxuta em push e pull request para
`main`, além de uma rodada semanal: gera uma CA local efêmera, valida o Compose,
reconstrói a imagem `quality` sem cache e a executa sem segredos de runtime.
CodeQL e Dependabot acompanham código, dependências Python, imagens Docker e
GitHub Actions; as atualizações minor/patch são agrupadas semanalmente. Esses controles não substituem
o percurso manual nem o bootstrap PostgreSQL exigidos para mudanças persistentes.

- [Arquitetura](docs/architecture.md)
- [Regras funcionais](docs/business-rules.md)
- [Desenvolvimento](docs/development.md)
- [Schema](migrations/README)
