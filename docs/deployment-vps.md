# Implantação no VPS

Esta implantação publica o MegaSena pelo Nginx em
`https://megasena-mspa.duckdns.org`. O Docker publica a aplicação apenas em
`127.0.0.1:5101` e o PostgreSQL apenas em `127.0.0.1:5102`; não abra essas
portas no firewall ou na OCI.

O código no VPS é um espelho do `main`: toda mudança nasce na máquina de
desenvolvimento, vai ao GitHub e só então chega ao servidor. O servidor não é
lugar de editar código — `~/deploy.sh` recusa implantar se encontrar alteração
não commitada.

## Primeira instalação

No VPS, instale Docker Engine e o plugin Compose pela fonte oficial do Docker.
Depois, clone o repositório e crie os arquivos locais que não são versionados:

O repositório é privado. O VPS lê-o por uma *deploy key* somente-leitura,
registrada no GitHub em **Settings → Deploy keys** e apontada pelo apelido
`github-megasena` em `~/.ssh/config`:

```
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
mkdir -p .secrets .certs
umask 077
openssl rand -hex 32 > .secrets/postgres_password.txt
openssl rand -hex 48 > .secrets/secret_key.txt
touch .certs/local-root-ca.crt
sudo chown root:root .secrets/postgres_password.txt
sudo chmod 0444 .secrets/postgres_password.txt
sudo chown 999:999 .secrets/secret_key.txt
sudo chmod 0400 .secrets/secret_key.txt
```

O diretório `.secrets/` continua privado para `ubuntu`; a senha do PostgreSQL
é montada de forma somente leitura em dois contêineres, por isso precisa ser
legível por ambos. A chave de sessão é legível somente pelo usuário da aplicação.

Instale Certbot e emita o certificado. A porta 80 precisa estar acessível pela
internet para a validação HTTP inicial:

```bash
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d megasena-mspa.duckdns.org
```

Instale a configuração TLS do proxy e valide o Nginx antes de ativá-la:

```bash
sudo install -m 0644 deploy/nginx/megasena.conf /etc/nginx/sites-available/megasena
sudo ln -s /etc/nginx/sites-available/megasena /etc/nginx/sites-enabled/megasena
sudo nginx -t
sudo systemctl reload nginx
```

Suba a aplicação e crie o primeiro usuário:

```bash
sudo docker compose --env-file .env.vps -f compose.yaml up --build -d
sudo docker compose --env-file .env.vps -f compose.yaml exec app flask --app run.py criar-usuario
```

Confira os serviços e a URL pública:

```bash
sudo docker compose --env-file .env.vps -f compose.yaml ps
curl -I http://127.0.0.1:5101/
curl -I http://megasena-mspa.duckdns.org/
curl -I https://megasena-mspa.duckdns.org/
sudo systemctl status certbot.timer
```

## Atualização

Antes de atualizar, gere um backup do PostgreSQL no próprio VPS:

```bash
mkdir -p instance/backups
sudo docker compose --env-file .env.vps -f compose.yaml exec -T postgres \
  pg_dump -U mega_sena -d mega_sena -Fc > instance/backups/mega_sena-$(date +%Y%m%dT%H%M%S).dump
```

A implantação é feita por `~/deploy.sh`, que confere a árvore, traz o `main`,
reconstrói a imagem, espera os health checks e valida o endereço público:

```bash
~/deploy.sh megasena --check   # mostra o que mudaria, sem alterar nada
~/deploy.sh megasena           # implanta
~/deploy.sh --status           # estado dos quatro projetos do VPS
```

O script aborta quando encontra alteração não commitada no servidor. Nesse caso
a correção é levar a mudança para a máquina de desenvolvimento, commitar e
enviar ao GitHub — nunca commitar no VPS.

## Rollback

Para voltar a uma revisão já validada, preserve o backup, selecione a revisão e
suba novamente:

```bash
git log --oneline -5
git checkout <commit-validado>
sudo docker compose --env-file .env.vps -f compose.yaml up --build -d
```

Esse estado é destacado (`detached HEAD`); a implantação seguinte pelo
`deploy.sh` volta a alinhar o servidor com o `main`.

Não use `docker compose down --volumes`: o volume contém o banco de dados.
