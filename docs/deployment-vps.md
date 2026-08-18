# Implantação de teste no VPS

Esta implantação publica o MegaSena somente pelo Nginx em
`http://megasena-mspa.duckdns.org`. O Docker publica a aplicação apenas em
`127.0.0.1:5101` e o PostgreSQL apenas em `127.0.0.1:5102`; não abra essas
portas no firewall ou na OCI.

## Primeira instalação

No VPS, instale Docker Engine e o plugin Compose pela fonte oficial do Docker.
Depois, clone o repositório e crie os arquivos locais que não são versionados:

```bash
mkdir -p ~/apps
git clone https://github.com/MSPA-Coder/mega-sena.git ~/apps/mega-sena
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

Instale a configuração do proxy e valide o Nginx antes de ativá-la:

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
```

## Atualização e rollback

Antes de atualizar, gere um backup do PostgreSQL no próprio VPS:

```bash
mkdir -p instance/backups
sudo docker compose --env-file .env.vps -f compose.yaml exec -T postgres \
  pg_dump -U mega_sena -d mega_sena -Fc > instance/backups/mega_sena-$(date +%Y%m%dT%H%M%S).dump
```

Atualize a revisão já validada e reconstrua a imagem:

```bash
git fetch origin
git pull --ff-only origin main
sudo docker compose --env-file .env.vps -f compose.yaml up --build -d
```

Para voltar ao commit anterior, primeiro preserve o backup, depois selecione a
revisão desejada e suba novamente:

```bash
git log --oneline -5
git checkout <commit-validado>
sudo docker compose --env-file .env.vps -f compose.yaml up --build -d
```

Não use `docker compose down --volumes`: o volume contém o banco de dados.
