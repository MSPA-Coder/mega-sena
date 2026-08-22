# Operação, dados e backup

## Topologia atual

O MegaSena roda em um VPS Oracle com Ubuntu, atrás de Nginx e TLS, em
<https://megasena-mspa.duckdns.org>. O Compose publica a aplicação e o
PostgreSQL somente no loopback, respectivamente nas portas 5101 e 5102; apenas
80 e 443 devem ficar expostas à internet.

O checkout em `/home/ubuntu/apps/mega-sena` é um espelho do branch `main`. Toda
mudança nasce na máquina de desenvolvimento, passa pelo GitHub e chega ao VPS
por `~/deploy.sh megasena`. Não edite, commite nem faça merge no servidor. A
deploy key é somente leitura e o script recusa uma árvore suja.

Os dados vivem no volume Docker `mega-sena_postgres_data`, fora do checkout.
`.secrets/` e `.certs/` também não são versionados e precisam ser preservados ou
restaurados em um reclone. Nunca use `docker compose down --volumes` no VPS.

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
install -d -m 0700 .secrets .certs
umask 077
openssl rand -hex 32 > .secrets/postgres_password.txt
openssl rand -hex 48 > .secrets/secret_key.txt
chmod 0444 .secrets/postgres_password.txt .secrets/secret_key.txt
touch .certs/local-root-ca.crt
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
~/deploy.sh megasena --check
~/deploy.sh megasena
~/deploy.sh --status
```

Depois da implantação, confira os health checks do Compose, o login e o fluxo
afetado. O `deploy.sh` central reverte automaticamente código e imagem quando o
build ou os health checks falham; não intervenha manualmente no checkout do
VPS.

Essa reversão não desfaz migrations já aplicadas. Toda mudança de schema deve
ter backup verificado e ser retrocompatível com a revisão anterior durante a
implantação, ou trazer um plano operacional manual de recuperação/restauração.
Trocar apenas código ou imagem nunca é tratado como rollback suficiente de uma
migration incompatível.
