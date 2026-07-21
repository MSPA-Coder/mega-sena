# Regras de negocio

## Estado da geracao

- URL e formularios sao a fonte de verdade dos parametros da tela de apostas.
- Filtros nao sao persistidos em sessao ou `localStorage`.
- Quando nenhum estado e informado na URL, os defaults vem da tabela `Config`.
- `quantity` aceita valores de 6 a 15 e `amount` de 1 a 100.
- `GenerationCriteria` e a fonte canonica de limites e regras cruzadas.

## Filtros

Filtros vazios nao eliminam jogos. Os criterios disponiveis sao:

- maior sequencia consecutiva;
- quantidade minima e maxima de pares;
- soma minima e maxima;
- quantidade minima de faixas ocupadas;
- quantidade maxima de dezenas na mesma faixa.

Para apostas com 7 a 15 dezenas, todos os subconjuntos cobertos de seis dezenas
devem obedecer aos filtros. Essa regra preserva a coerencia da cobertura
`C(n, 6)` apresentada ao usuario.

Filtros da lista de concursos sao independentes dos filtros de geracao.

## Geracao e fechamento

- A geracao aleatoria usa `secrets.SystemRandom`.
- Resultados historicos identicos sao evitados em apostas de seis dezenas.
- Existe controle de diversidade entre apostas do mesmo lote.
- Filtros restritivos podem produzir menos apostas que o solicitado.
- Fechamento matematico nao sorteia candidatos: enumera todas as combinacoes de
  seis dezenas dentro do conjunto-base.
- O conjunto-base deve conter entre 6 e 15 dezenas distintas, todas entre 1 e 60.

## Persistencia das apostas

- Apostas sao normalizadas e deduplicadas dentro de cada lote.
- Um lote aceita no maximo `C(15, 6) = 5.005` apostas.
- Cada lote recebe um `generation_id` compartilhado.
- A alocacao do identificador e serializada para o servidor Flask local.

## Importacao XLSX

- O upload aceita apenas `.xlsx`.
- Planilhas enviadas nao sao gravadas no projeto.
- A leitura e limitada a 10.000 linhas de dados.
- O arquivo ZIP interno e validado por quantidade de partes, tamanho expandido
  e taxa de compressao.
- Concursos existentes sao atualizados quando algum campo importado muda.
- Valores monetarios sao persistidos em centavos inteiros.
- Falhas de persistencia executam rollback da transacao.

## Banco e migracoes

- O banco local fica em `instance/mega_sena.db`.
- Banco novo e criado exclusivamente pelas migracoes Alembic.
- Banco legado so e marcado como migrado depois de validacao e backup integro.
- Upgrades futuros criam backup antes da alteracao do schema.
- Campos derivados dos concursos sao recalculados uma vez por versao do
  algoritmo.

## Seguranca e escopo

- Metodos mutantes exigem token CSRF.
- Hosts nao confiaveis sao rejeitados.
- A aplicacao aplica CSP e outros headers defensivos.
- O produto e local e single-user; nao existe autenticacao ou autorizacao de
  usuarios.
