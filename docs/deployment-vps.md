# Operação, dados e backup

## Entrega por imagem validada

No VPS, use somente `~/deploy.sh megasena` depois da instalação da
infraestrutura compatível de `manutencao/main`. `compose.release.yaml` recebe
`APP_IMAGE` e `POSTGRES_IMAGE` por digest; não execute um build Compose para
atualizar esse ambiente. O Compose base continua servindo ao desenvolvimento
AMD64 local, que é validação separada da entrega ARM64.

A CI nativa ARM64 constrói um runtime e um PostgreSQL. `Dockerfile.verify`
adiciona ferramentas sobre o candidato e confere que as versões de runtime
não mudaram. Ruff/mypy/pytest, Chromium e Trivy validam os candidatos;
`Runtime contracts` recebe esses mesmos IDs via artefato para conferir
imutabilidade, health e papel restrito (app/migrate). Só depois dos dois jobs,
o job de publicação envia os mesmos IDs ao GHCR, sem reconstruir.

Pacotes: `ghcr.io/mspa-coder/mega-sena` e `mega-sena-postgres`, tags
`run-<run_id>-<tentativa>`. Visibilidade pública só após conferir conteúdo
publicável; nenhuma conta, .env, .secrets, chave privada ou fixture entra no
runtime. Repositório público não torna um pacote automaticamente público.

O deploy exige run completo verde de main no SHA exato, revisão/run e
arquitetura em **ambas** as imagens. Confere os IDs anteriores disponíveis
antes de alterar código/serviços; depois sobe `--no-build --pull never`.
Rollback restaura IDs por papel e código, nunca dados/schema. Só o serviço
PostgreSQL recebe `mspa.backup.postgres=true`, preservando a descoberta do
backup mesmo com digest ou ID local. `--refresh` escolhe o novo run verde do
mesmo commit. Aguarde a publicação de main antes de implantar.

## Topologia atual

O MegaSena roda em um VPS Oracle com Ubuntu, atrás de Nginx e TLS, em
<https://megasena-mspa.duckdns.org>. O Compose publica a aplicação e o
PostgreSQL somente no loopback, respectivamente nas portas 5101 e 5102; apenas
80 e 443 devem ficar expostas à internet.

O checkout em `/home/ubuntu/apps/mega-sena` é um espelho do branch `main`. Toda
mudança nasce na máquina de desenvolvimento, passa pelo GitHub e chega ao VPS
por `~/deploy.sh megasena`. Não edite, commite nem faça merge no servidor. A
deploy key é somente leitura e o script recusa uma árvore suja.

Publique por branch, pull request com checks obrigatórios verdes e squash merge;
só então o `main` remoto é elegível para o deploy. Não faça push direto ao
`main`; aguarde a CI de main publicar os artefatos daquele SHA. A CI de PR
não publica nem substitui o run de entrega que o deploy confere.

Os dados vivem no volume Docker `mega-sena_postgres_data`, fora do checkout.
`.secrets/` também não é versionado e precisa ser preservado ou restaurado em um
reclone. `.certs/local-root-ca.crt` só é necessário se o host do VPS intercepta
HTTPS durante o build; nesse caso, preserve/restaure a raiz CA correspondente.
Nunca use `docker compose down --volumes` no VPS.

## Primeira instalação

Instale Docker Engine e o plugin Compose pelos canais oficiais. Configure no
GitHub uma deploy key somente leitura e use um host SSH dedicado:

```text
Host github-megasena
    HostName github.com
    User git
    IdentityFile ~/.ssh/deploy_megasena
    IdentitiesOnly yes
```

```bash
mkdir -p ~/apps
git clone git@github-megasena:MSPA-Coder/mega-sena.git ~/apps/mega-sena
cd ~/apps/mega-sena
cp .env.vps.example .env.vps
install -d -m 0700 .secrets
umask 077
openssl rand -hex 32 > .secrets/postgres_password.txt
openssl rand -hex 32 > .secrets/postgres_app_password.txt
openssl rand -hex 48 > .secrets/secret_key.txt
chmod 0444 .secrets/postgres_password.txt .secrets/postgres_app_password.txt .secrets/secret_key.txt
```

Os redirecionamentos gravam os valores sem exibi-los. Mantenha `.secrets/` com
modo `0700`, pertencente ao usuário de deploy, e os dois arquivos com modo
`0444`. No host, os demais usuários não conseguem atravessar o diretório; nos
contêineres, o Compose monta cada arquivo somente nos serviços que declaram o
secret. Assim, a senha do PostgreSQL fica visível para `postgres` e `app`, e a
chave de sessão somente para `app`, sem depender de um UID numérico estável.

Fora do modo Swarm, os secrets do Compose são arquivos montados do host, não um
cofre ou mecanismo de distribuição criptografada. Por isso, a proteção depende
da permissão `0700` do diretório no host, da montagem seletiva em
`compose.yaml` e de não conceder o secret a outros serviços. Depois de mudar a
imagem base, o usuário de runtime ou a declaração de secrets, confira que os
serviços necessários continuam lendo os arquivos sem imprimir seu conteúdo.

Instale Certbot e emita o certificado:

```bash
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d megasena-mspa.duckdns.org
```

Instale o virtual host pelo procedimento central versionado em
`_manutencao/vps/nginx`. A configuração ativa precisa preservar a zona
`limit_req` compartilhada aplicada ao `POST /login`; os contadores em memória
dos workers Gunicorn não a substituem. Valide a sintaxe com `nginx -t` antes de
recarregar o serviço.

Suba os serviços e provisione o primeiro acesso:

```bash
sudo docker compose --env-file .env.vps -f compose.yaml up --build -d
sudo docker compose --env-file .env.vps -f compose.yaml exec app flask --app run.py criar-usuario
sudo docker compose --env-file .env.vps -f compose.yaml ps
curl -I https://megasena-mspa.duckdns.org/
```

## Backup e restauração

Backup, catálogo, verificação e ensaio de restauração são responsabilidade do
projeto irmão BackupRestore. Este repositório não contém script próprio de
backup ou restauração. Antes de manutenção de dados, migration ou implantação
que possa alterar o schema, execute no ambiente do BackupRestore:

```powershell
python cli.py backup --projeto mega_sena --tipos banco
```

Considere o backup concluído somente quando o BackupRestore registrar a
verificação prevista por ele. Agendamento, retenção, localização dos artefatos e
procedimento de restauração pertencem à documentação e à configuração desse
projeto central; não mantenha uma segunda receita aqui. A existência do volume
Docker não substitui backup.

## Implantação e mudanças de schema

```bash
~/deploy.sh megasena
```

Depois da implantação, confira o login e o fluxo afetado. O próprio
`deploy.sh` confere a elegibilidade do commit, os health checks e o endereço
público, e reverte automaticamente código e imagem quando build ou saúde
falham; não intervenha manualmente no checkout do VPS. `~/deploy.sh --status`
continua disponível apenas para diagnóstico transversal.

Essa reversão não desfaz migrations já aplicadas. Toda mudança de schema deve
ter backup verificado e ser retrocompatível com a revisão anterior durante a
implantação, ou trazer um plano operacional manual de recuperação/restauração.
Trocar apenas código ou imagem nunca é tratado como rollback suficiente de uma
migration incompatível.
