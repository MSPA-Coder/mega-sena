# Desenvolvimento

## Ambiente

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Execute a aplicacao com:

```powershell
python run.py
```

## Qualidade

Antes de cada commit:

```powershell
python -m pytest -q
python -m ruff check app migrations scripts tests run.py
```

Para auditar dependencias de runtime:

```powershell
python scripts/audit_dependencies.py
```

Os testes sao organizados por nivel:

```text
tests/unit/          funcoes puras e Value Objects
tests/integration/   banco, importacao e servicos
tests/web/           contratos HTTP, templates, seguranca e design system
```

Fixtures e builders compartilhados ficam em `tests/conftest.py` e
`tests/support.py`.

## Migracoes

O schema e controlado por Flask-Migrate/Alembic. Nunca use `db.create_all()` no
bootstrap de producao como substituto de migracoes.

Ao alterar modelos:

```powershell
flask --app run.py db migrate -m "descricao"
flask --app run.py db upgrade
python -m pytest -q tests/integration/test_migrations.py
```

Revise manualmente a migracao gerada antes do commit.

## Evolucao dos filtros

Para adicionar um criterio de geracao:

1. Inclua o campo, limite e normalizacao em `app/bets/criteria.py`.
2. Implemente sua avaliacao em `GenerationCriteria`.
3. Atualize a distribuicao combinatoria e a descricao do racional.
4. Atualize defaults persistidos em `app/settings/service.py`.
5. Inclua o campo nos formularios e JavaScript da pagina de apostas.
6. Adicione testes unitarios, de integracao e web quando aplicavel.

Evite espalhar condicionais com o nome do filtro em novos modulos; a politica
de aceitacao deve continuar centralizada no objeto de criterios.

## Dependencias entre camadas

- Rotas podem importar servicos e componentes de apresentacao.
- Rotas nao devem importar modelos ou `db.session`.
- `core` nao deve depender de Flask-SQLAlchemy.
- Servicos sao responsaveis pelos limites transacionais dos casos de uso.
- Imports novos nao devem usar os modulos de compatibilidade
  `app/routes.py` ou `app/generation_params.py`.

## CI

`.github/workflows/ci.yml` executa Ruff e pytest em Python 3.11 e 3.13 para
pushes e pull requests. A auditoria de dependencias roda semanalmente e por
acionamento manual.
