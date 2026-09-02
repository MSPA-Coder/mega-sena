# ADR 0002 — Acervo comum sem dono (MS-04)

## Decisão

Apostas geradas, concursos e configurações são acervo comum. Qualquer conta
autenticada — inclusive `operador`, o papel padrão de toda conta nova — cria,
edita e apaga qualquer registro desse acervo: `POST /bets/saved/<id>/delete`
apaga aposta salva de qualquer pessoa, e `POST /contests/import` /
`POST /contests/import-link` reescrevem o acervo compartilhado de concursos,
nenhum dos três exigindo `admin`. O papel só separa administração (contas,
Configurações, `POST /reset`) de operação — nunca particiona os dados
financeiros em si. Nenhuma tabela de domínio (`Draw`, `GeneratedBet`, `Config`)
tem coluna de proprietário em nenhuma das 5 revisões Alembic.

## Motivo

O sistema é de uso individual do mantenedor (ver README.md). Introduzir
`owner_id`/`user_id` em apostas ou concursos teria impacto de produto e de
migração sem leitor: não há, hoje, uma segunda pessoa cujo acervo precise ficar
isolado do da primeira.

## Alternativa considerada e recusada, por ora

Coluna `owner_id` em `generated_bets`, com filtro por `current_user` em
`list_recent_generations_with_bets` e em `delete_saved_bet`. Recusada agora
porque o custo de migração (mais o de reescrever as duas consultas e decidir o
que fazer com o acervo de concursos, que não tem correspondente individual
natural) não se paga sem uso real por mais de uma pessoa.

## Gatilho de revisão

**A primeira vez que uma segunda pessoa receber conta própria no sistema.**
Nesse momento, "`operador` não administra o sistema" deixa de ser sinônimo
aceitável de "`operador` tem acesso irrestrito ao acervo financeiro de
qualquer outra conta", e a alternativa acima — ou a restrição das exclusões
destrutivas a `admin`, sem introduzir dono — precisa ser reavaliada antes de
conceder a segunda conta.

## Plano de migração, se revisado

Revisão Alembic acrescentando `owner_id` (FK para `users`, nulável) em
`generated_bets`, com backfill apontando para a conta administrativa
existente. `list_recent_generations_with_bets` e `delete_saved_bet` passam a
filtrar por `current_user.id` a menos que o ator seja `admin`. Concursos
(`Draw`) permanecem acervo comum mesmo nesse cenário — são fato público
(resultado oficial do sorteio), não dado pessoal de quem os importou.

## Fora de escopo

Esta decisão não altera `POST /reset` (já exige `admin` e é auditado) nem a
proteção do último administrador (ADR 0001). Não há mudança de comportamento
nesta revisão: é registro de uma decisão já em vigor, não uma correção de
código.
