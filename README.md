# Mega Sena AI

Aplicacao Flask local para importar resultados historicos da Mega Sena, consultar
estatisticas e gerar apostas com filtros configuraveis. O sistema nao tenta
prever sorteios: ele organiza dados, calcula metricas e apresenta cobertura
combinatoria.

## Inicio rapido

Requisitos: Python 3.11 ou superior e `pip`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

A aplicacao fica disponivel em `http://127.0.0.1:5000`. Fora de desenvolvimento,
defina a variavel de ambiente `SECRET_KEY` e configure `TRUSTED_HOSTS` para os
hosts aceitos.

## Funcionalidades

- Importacao segura de planilhas `.xlsx` com resultados historicos.
- Dashboard de frequencias, atrasos, somas, paridade, sequencias e premiacoes.
- Geracao de apostas de 6 a 15 dezenas com criterios configuraveis.
- Fechamento matematico de 6 a 15 dezenas-base.
- Calculo da cobertura combinatoria e chance aproximada.
- Persistencia de lotes de apostas geradas.
- Migracoes automaticas e backup de bancos SQLite legados.
- CSRF, validacao de host e headers HTTP defensivos.

## Documentacao

- [Arquitetura](docs/architecture.md): modulos, dependencias e patterns adotados.
- [Regras de negocio](docs/business-rules.md): contratos que devem ser preservados.
- [Desenvolvimento](docs/development.md): ambiente, testes, lint, migracoes e CI.

## Estrutura resumida

```text
app/
|-- bets/          # criterios, geracao e combinatoria
|-- core/          # seguranca, parsing numerico e formatacao
|-- draws/         # importacao, consultas e estatisticas
|-- settings/      # configuracao persistida e manutencao
|-- web/           # rotas Flask organizadas por funcionalidade
|-- static/css/    # estilos modulares
|-- templates/     # paginas e componentes Jinja
|-- extensions.py
|-- models.py
`-- schema.py
tests/
|-- unit/
|-- integration/
`-- web/
migrations/
scripts/
`-- audit_dependencies.py
```

## Verificacao rapida

```powershell
python -m pytest -q
python -m ruff check app migrations scripts tests run.py
python scripts/audit_dependencies.py
```

O workflow de CI executa pytest e Ruff em Python 3.11 e 3.13. A auditoria de
dependencias e executada semanalmente ou por acionamento manual.
