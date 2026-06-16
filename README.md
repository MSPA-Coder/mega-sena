# Mega Sena AI

Aplicação web em Flask para importar resultados históricos da Mega Sena, analisar estatísticas dos concursos e gerar apostas com filtros configuráveis.

O projeto combina uma base local SQLite, importação de planilhas `.xlsx`, painéis estatísticos e um gerador de apostas que usa aleatoriedade segura do Python (`secrets.SystemRandom`). A proposta é apoiar estudo e organização de jogos, não prever resultados.

## Funcionalidades

- Importação de resultados históricos da Mega Sena a partir de planilhas `.xlsx`.
- Dashboard com frequência de dezenas, atrasos, pares, trios, soma, paridade, sequências, faixas e premiações.
- Consulta de concursos importados com filtros de histórico.
- Geração de apostas de 6 a 15 dezenas com parâmetros configuráveis.
- Filtros por quantidade de pares, soma das dezenas, maior sequência consecutiva e distribuição por faixas.
- Prévia de quantos concursos históricos passariam pelos filtros escolhidos.
- Relatório de racional matemático com combinações eliminadas e restantes.
- Fechamento matemático a partir de um conjunto-base de 6 a 15 dezenas.
- Salvamento de apostas em lotes agrupados por geração.

## Tecnologias

- Python
- Flask
- Flask-SQLAlchemy
- SQLite
- OpenPyXL
- NumPy
- Pytest

## Requisitos

- Python 3.11 ou superior
- `pip`
- Ambiente virtual recomendado

O projeto foi usado localmente com PyCharm 2026.1, mas também roda pelo terminal.

## Como Rodar

Clone o repositório:

```bash
git clone https://github.com/MSPA-Coder/mega-sena.git
cd mega-sena
```

Crie e ative um ambiente virtual:

```bash
python -m venv .venv
```

No Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

No Linux ou macOS:

```bash
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Inicie a aplicação:

```bash
python run.py
```

Acesse:

```text
http://127.0.0.1:5000
```

## Banco de Dados

A aplicação usa SQLite local em:

```text
instance/mega_sena.db
```

Na primeira execução, as tabelas e configurações padrão são criadas automaticamente. A pasta `instance/` fica fora do Git para evitar versionar dados locais.

## Importação de Resultados

A tela `/import` aceita planilhas `.xlsx` com os concursos históricos.

A importação reconhece colunas por nomes normalizados, incluindo campos como:

- concurso
- data do sorteio
- bola/dezena 1 a 6
- ganhadores da Sena, Quina e Quadra
- rateios e valores acumulados

Ao importar novamente uma planilha, concursos existentes são atualizados quando algum campo muda. Registros inválidos ou duplicados na mesma importação são ignorados.

## Geração de Apostas

A tela `/bets` permite gerar apostas usando:

- quantidade de apostas a gerar
- quantidade de dezenas por aposta, configurada entre 6 e 15
- mínimo e máximo de dezenas pares
- soma mínima e máxima
- limite de maior sequência consecutiva
- mínimo de faixas ocupadas entre `01-10`, `11-20`, `21-30`, `31-40`, `41-50` e `51-60`
- máximo de dezenas concentradas na mesma faixa

O gerador:

- usa `secrets.SystemRandom().sample()` para montar candidatos;
- evita repetir concursos históricos quando a aposta tem 6 dezenas;
- aplica somente os filtros informados;
- controla diversidade entre apostas geradas no mesmo lote;
- permite revisar as apostas antes de gravá-las no banco.

## Rotas Principais

- `/dashboard`: painel estatístico.
- `/bets`: geração, fechamento e salvamento de apostas.
- `/rationale`: racional matemático dos filtros ativos.
- `/contests`: consulta de concursos importados.
- `/import`: importação de planilha e configurações.
- `/api/combinations`: relatório combinatório em JSON.
- `/api/draw-filter-preview`: prévia de concursos históricos que passam nos filtros.
- `/api/filter-targets`: sugestão de parâmetros por percentual alvo.

## Testes

Execute:

```bash
py -m pytest
```

Ou, dependendo do ambiente:

```bash
python -m pytest
```

Os testes cobrem importação de planilhas, métricas estatísticas, filtros, combinações, endpoints e salvamento de apostas.

## Estrutura do Projeto

```text
.
|-- app/
|   |-- __init__.py
|   |-- models.py
|   |-- routes.py
|   |-- services.py
|   |-- static/
|   |   `-- style.css
|   `-- templates/
|-- tests/
|   `-- test_app.py
|-- context.md
|-- requirements.txt
|-- run.py
`-- README.md
```

## Aviso Importante

A Mega Sena é um evento aleatório. Este sistema não prevê sorteios, não aumenta matematicamente a probabilidade real de acerto além da cobertura combinatória das apostas feitas e não deve ser usado como promessa de ganho financeiro.

Use a aplicação como ferramenta de estudo, organização e simulação estatística.
