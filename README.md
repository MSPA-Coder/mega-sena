# MegaSena

Aplicação para importar resultados da Mega-Sena, consultar estatísticas e
organizar apostas e fechamentos. É uma ferramenta de apoio e controle, hoje
usada somente pelo mantenedor. Frequências, filtros e relatórios descrevem o
histórico carregado: não preveem sorteios nem aumentam a chance matemática de
ganho.

O sistema é um monólito modular em Flask, com HTML renderizado no servidor,
interações HTMX, SQLAlchemy/Alembic e PostgreSQL. O ambiente oficial de execução
e validação é Docker Compose; não é necessário instalar Python ou PostgreSQL no
host.

## Execução local

```powershell
Copy-Item .env.docker.example .env.docker
.\scripts\provision_secrets.ps1
.\scripts\export_local_ca.ps1
docker compose --env-file .env.docker -f compose.yaml up --build -d
```

A aplicação fica em <http://127.0.0.1:5101>. O entrypoint aplica todas as
migrations pendentes antes de iniciar o Gunicorn. Os dados permanecem no volume
`postgres_data` após `docker compose down`; `down -v` os remove e só deve ser
usado para descarte deliberado.

Crie o primeiro usuário dentro do contêiner:

```powershell
docker compose --env-file .env.docker -f compose.yaml exec app flask --app run.py criar-usuario
```

O primeiro usuário recebe o papel de administrador. A tela `/usuarios` é
restrita a administradores; novos usuários criados por ela são operadores por
padrão e continuam compartilhando o mesmo acervo de concursos, apostas e
configurações.

Para desenvolvimento com o código montado no contêiner, acrescente
`-f compose.dev.yaml` ao comando de subida. O Compose padrão usa a imagem
imutável.

## Validação

```powershell
docker compose --env-file .env.docker -f compose.yaml --profile quality run --build --rm quality
```

`--build` faz parte do comando: o serviço `quality` não monta o código do
host e `docker compose run` só reconstrói quando a imagem não existe. Sem
ele, a validação roda a versão anterior do código e passa em verde.

Esse estágio executa Ruff e pytest. Mudanças relevantes também exigem percorrer
manualmente o fluxo afetado; alterações persistentes exigem backup e validação
das migrations em PostgreSQL vazio.

## Documentação

- [Arquitetura e responsabilidades](docs/architecture.md)
- [Regras do domínio](docs/business-rules.md)
- [Desenvolvimento e validação](docs/development.md)
- [Operação, dados e backup](docs/deployment-vps.md)
- [Migrations e schema](migrations/README)
