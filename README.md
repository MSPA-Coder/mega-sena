# Mega Sena AI

Aplicação web local para importar resultados da Mega-Sena, explorar estatísticas
e montar apostas com critérios configuráveis. O projeto não prevê sorteios nem
promete vantagem estatística: frequências históricas e filtros servem para
análise e organização das combinações.

## Principais recursos

- importação de resultados por planilha `.xlsx`;
- dashboard com frequência, soma, paridade, sequências e premiações;
- consulta e filtragem dos concursos importados;
- geração aleatória de apostas com critérios opcionais;
- fechamento completo a partir de um conjunto de dezenas;
- relatório do universo combinatório e da cobertura das apostas;
- gravação e consulta dos lotes gerados;
- configuração de valores padrão pela própria interface.

## Executar localmente

Requisitos: Python 3.11 ou superior e `pip`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

Acesse `http://127.0.0.1:5000`. Na primeira execução, a aplicação cria e
atualiza o banco SQLite em `instance/mega_sena.db` por meio das migrações.

Para desenvolver, instale também as ferramentas de teste e lint:

```powershell
python -m pip install -r requirements-dev.txt
```

## Fluxo de uso

1. Em **Concursos**, importe uma planilha `.xlsx` com os resultados.
2. Consulte o dashboard e a lista de concursos.
3. Em **Apostas**, ajuste os critérios ou informe as dezenas de um fechamento.
4. Revise as combinações geradas e grave apenas os lotes que quiser conservar.
5. Em **Configurações**, altere os valores iniciais usados pela tela de apostas.

## Escopo atual

O sistema foi projetado para uso local e individual, com SQLite e sem cadastro
de usuários. A interface aceita apostas e fechamentos de 6 a 15 dezenas; esse é
um limite operacional do aplicativo, não uma descrição das regras oficiais da
Mega-Sena. A importação aceita somente `.xlsx`.

Se a aplicação for exposta fora da máquina local, use um servidor WSGI adequado
e defina uma `SECRET_KEY` estável e secreta. O servidor embutido de `run.py` é
destinado ao uso local.

## Documentação

- [Arquitetura](docs/architecture.md): organização e responsabilidades atuais.
- [Regras funcionais](docs/business-rules.md): comportamento observado pelo usuário.
- [Desenvolvimento](docs/development.md): ambiente, testes, migrações e critérios de manutenção.

## Estrutura

```text
app/
|-- bets/          # critérios, geração e cálculos combinatórios
|-- core/          # utilitários compartilhados e segurança HTTP
|-- draws/         # importação, consultas e estatísticas
|-- settings/      # configurações e manutenção dos dados
|-- web/           # rotas e adaptação HTTP
|-- static/        # JavaScript e CSS
|-- templates/     # páginas e componentes Jinja
|-- models.py      # modelos persistidos
`-- schema.py      # inicialização, migrações e backups do banco
docs/
migrations/
scripts/
tests/
```

## Verificação

```powershell
python -m pytest -q
python -m ruff check app migrations scripts tests run.py
python scripts/audit_dependencies.py
```

O CI executa Ruff e pytest com Python 3.11 e 3.13. A auditoria de dependências
é executada no acionamento manual do workflow e na rotina semanal.
