# Travas de banco

Inventário das travas (`with_for_update`, `pg_advisory_xact_lock`, `LOCK TABLE`) que protegem apostas,
concursos, configuração e acesso, e de **qual teste ou qual outra garantia** responde por cada uma. A regra está
em `docs/TESTES.md` (T7 e T11): trava nova nasce com teste de disputa que falha quando ela é retirada, ou com uma
linha aqui dizendo qual garantia a cobre.

Medido em 29/10/2026 retirando cada trava numa cópia do commit e rodando o arquivo de disputa 5 vezes (receita
em T11). "Detectada" quer dizer que o teste falhou em todas as repetições sem a trava.

Os testes de `tests/test_travas_postgres.py` seguem um padrão: uma "primeira operação" muda o estado e fica aberta
(sem confirmar); a operação testada precisa esperar por ela e então enxergar o estado confirmado. Não dependem de
sorte de tempo.

| Trava | Protege | Cobertura |
|---|---|---|
| `accounts/service.py` `_lock_user_policy` (advisory) | nunca ficar sem administrador | `test_commands_atomic.py::test_dois_administradores_nao_removem_ambos_os_papeis_em_concorrencia` (detectada) |
| `bets/service.py` trava do token da confirmação (advisory) | a mesma confirmação enviada duas vezes grava um lote só | `test_commands_atomic.py::test_segunda_confirmacao_com_o_mesmo_token_espera_a_primeira_terminar` (determinístico, detectada) e `test_concurrent_confirmation_preserves_batch_and_event_identity` (corrida; só percebe quando roda sozinho) |
| `bets/service.py` `stage_delete_bet` (`with_for_update`) | excluir aposta que outra transação já excluiu devolve erro explícito | `test_travas_postgres.py::test_excluir_aposta_ja_excluida_por_outra_transacao_e_recusado` (detectada) |
| `draws/importing.py` `_acquire_import_lock` (advisory) | duas importações não inserem o mesmo concurso | `test_travas_postgres.py::test_importacao_espera_a_outra_importacao_e_nao_repete_o_concurso` (detectada) |
| `draws/importing.py` `_locked_existing_draws` (`with_for_update`) | decidir "atualizado ou ignorado" sobre o concurso já alterado | `test_travas_postgres.py::test_importacao_espera_a_linha_do_concurso_e_decide_sobre_o_estado_novo` (detectada) |
| `settings/service.py` `LOCK TABLE config` | dois primeiros salvamentos não disputam o mesmo `INSERT` | `test_travas_postgres.py::test_primeiro_salvamento_de_configuracao_espera_o_outro_e_atualiza_em_vez_de_inserir` e `test_salvamento_de_configuracao_espera_a_gravacao_em_andamento_das_linhas_existentes` (detectada) |
| `settings/service.py` linhas de `Config` (`with_for_update`) | ler e gravar as linhas existentes | **Coberta por** `LOCK TABLE config IN SHARE ROW EXCLUSIVE MODE`, tomado antes na mesma transação: todo escritor da tabela pede pelo menos `ROW EXCLUSIVE`, que esse modo recusa. Retirada sozinha, os dois testes de configuração seguem passando (0/5), como esperado. |
