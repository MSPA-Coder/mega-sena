# Desenvolvimento

O projeto roda em Docker. O host precisa apenas de Docker Desktop, Git e um editor.

```powershell
Copy-Item .env.docker.example .env.docker
.\scripts\provision_secrets.ps1
.\scripts\export_local_ca.ps1
docker compose --env-file .env.docker -f compose.yaml up --build -d
```

O provisionamento cria `.secrets/postgres_password.txt` e
`.secrets/secret_key.txt`, sem mostrar seus valores. Para migrar uma instalação
que ainda contém `POSTGRES_PASSWORD` e `SECRET_KEY` no `.env.docker`, execute o
mesmo comando e, só após validar a subida, repita com `-RemoveLegacyValues`.
Não use `-Force` sem tratar a rotação da senha no PostgreSQL e a invalidação de
sessões causada por trocar a chave.

A aplicação estará em <http://127.0.0.1:5101>. O modo padrão é imutável, sem
bind mount. Para edição local com código montado, inclua explicitamente o arquivo
de desenvolvimento:

```powershell
docker compose --env-file .env.docker -f compose.yaml -f compose.dev.yaml up --build -d
```

## Validação manual

Como o produto é de uso individual, a validação é deliberadamente curta:

1. Suba a aplicação e abra as telas afetadas.
2. Em alterações de schema, execute `flask db upgrade` em um PostgreSQL vazio e confirme que a aplicação inicia.
3. Antes de qualquer manutenção de dados ou schema aplicado, crie e confira um backup com `scripts/backup_postgres.ps1`.

## Alterações de schema

O schema atual está consolidado em uma baseline Alembic. Não altere a baseline que já representa bancos existentes. Quando uma alteração futura for realmente necessária, crie uma migration nova, faça backup e valide-a em banco vazio.

`create_app()` não altera schema nem grava dados. Em Docker, `docker-entrypoint.sh` aplica migrations antes de iniciar o servidor.
