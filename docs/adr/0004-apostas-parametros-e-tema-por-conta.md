# ADR 0004 — Apostas, padrões de geração e tema por conta

Estado: vigente.

Substitui o ADR 0002 no que diz respeito a apostas e configurações. Concursos
continuam acervo comum.

## Decisão

Tomada pelo mantenedor em 04/11/2026. O uso continua individual: em produção
só a conta do mantenedor tem atividade. A separação entra antes do gatilho do
ADR 0002 (a segunda pessoa com conta própria), e não depois, por dois motivos:

- é a visão de produto registrada pelo mantenedor em 24/08/2026 — no MegaSena,
  apostas, parâmetros e tema pertencem a cada usuário;
- com uma conta só, ela não muda nada no uso (tudo o que existe fica com essa
  conta), e a segunda conta, quando vier, já nasce isolada, sem migração de
  dados nem decisão urgente sobre de quem é cada aposta.

- **Apostas são de cada conta.** `generated_bets.owner_id` (FK para `users`,
  `RESTRICT`) é quem confirmou o lote. Minhas apostas, a conferência com o
  resultado e o aviso de apostas premiadas da importação mostram só as da
  conta logada; excluir aposta de outra conta responde como se ela não
  existisse. Não há exceção para `admin`: administrar o sistema não é ver as
  apostas dos outros.
- **Padrões de geração são de cada conta** (`user_config`, chave por conta e
  chave). Chave que a pessoa não salvou vale o padrão do sistema (`config`) e,
  na falta dele, o do código — assim cada conta começa com os valores que
  existiam quando os padrões eram de todos, sem linha semeada.
- **Tema claro/escuro é da conta** (`users.theme`), como o formato regional.
  Nulo enquanto a pessoa não escolhe; aí vale o cookie do navegador, que
  também é o que vale na tela de login.
- **Continua de `admin`:** o endereço da planilha de resultados
  (`POST /settings/sistema`), que vale para todos, e `POST /reset`, que apaga
  os concursos e as apostas de **todas** as contas. Para os demais, essas
  seções não aparecem e as rotas respondem 403.
- Contas continuam sendo criadas só por `admin` (tela e CLI), sem
  auto-cadastro (ADR 0001).

## Migração

Revisão `20261104_0011_owner_per_user`. As apostas que já existiam vão para a
conta `admin` de menor id — em produção, a única com atividade. Com apostas
gravadas e nenhuma conta `admin`, a revisão para sem alterar nada, porque não
há a quem entregá-las.

## Consequências

- Uma pessoa que hoje entra com o login de outra precisa da própria conta;
  senão as apostas dela continuam aparecendo como da outra.
- Conta não se apaga (só se desativa): o `RESTRICT` impede que apagar uma
  conta leve junto as apostas dela.
- Concursos seguem comuns: são o resultado público do sorteio, não dado de
  quem os importou.
