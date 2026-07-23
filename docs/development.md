# Desenvolvimento

## Ambiente

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python run.py
```

O projeto requer Python 3.11 ou superior.

## Verificações locais

Antes de entregar uma alteração, execute:

```powershell
python -m pytest -q
python -m ruff check app migrations scripts tests run.py
```

Para verificar vulnerabilidades conhecidas nas dependências de runtime:

```powershell
python scripts/audit_dependencies.py
```

O CI repete lint e testes em Python 3.11 e 3.13. A auditoria também é executada
semanalmente e pode ser acionada manualmente.

## Estratégia de testes

```text
tests/unit/          regras e cálculos sem infraestrutura
tests/integration/   banco, migrações, importação e serviços
tests/web/           comportamento HTTP, formulários e segurança
```

Um teste deve proteger comportamento útil e atual. Ao alterar uma funcionalidade:

- teste regras e casos de borda no nível mais baixo que ofereça confiança;
- prefira resultados observáveis a detalhes de implementação;
- mantenha testes de segurança, integridade de dados e contratos públicos;
- atualize ou remova o teste quando o requisito que ele representava deixar de
  existir.

Evite testes criados apenas para registrar uma fase de refatoração, como afirmar
que um texto “não existe mais”, que um elemento “foi movido” ou que um módulo
continua em determinado arquivo. Seletores CSS exatos, proporções de layout e
redirects de URLs antigas só devem ser fixados por teste quando forem requisitos
atuais de acessibilidade, usabilidade ou compatibilidade assumida.

Fixtures e builders compartilhados ficam em `tests/conftest.py` e
`tests/support.py`.

## Migrações

O schema é versionado com Flask-Migrate/Alembic. Depois de alterar um modelo:

```powershell
flask --app run.py db migrate -m "descrição"
flask --app run.py db upgrade
python -m pytest -q tests/integration/test_migrations.py
```

Revise a migração gerada: nomes de tabelas e índices, nulabilidade, valores
padrão, transformação de dados e caminho de upgrade. Não edite uma revisão já
aplicada para representar um novo estado; crie outra revisão.

Nos testes isolados, `db.create_all()` pode ser adequado para preparar um banco
efêmero quando o objeto do teste não é o processo de migração. A inicialização
normal da aplicação usa Alembic.

## Alterações em critérios de geração

Os campos e a normalização são centralizados em `app/bets/criteria.py`. Ao criar
ou mudar um critério, verifique os pontos afetados:

1. regra de normalização e avaliação;
2. geração aleatória e apostas com mais de seis dezenas;
3. relatório combinatório e racional exibido;
4. valores padrão persistidos;
5. formulário, URL e JavaScript da tela;
6. testes proporcionais ao risco da mudança.

Nem toda alteração exige teste em todos os níveis. Cubra a regra onde ela vive e
adicione um teste web quando houver um contrato HTTP ou fluxo de usuário novo.

## Limites operacionais

Antes de adicionar ou conservar um limite, identifique sua razão:

- validade do domínio, como dezenas entre 1 e 60;
- segurança, como tamanho e expansão de uploads;
- custo computacional, memória ou tamanho de resposta;
- clareza da interface.

Evite tratar como regra de negócio um número escolhido apenas para facilitar uma
implementação anterior. Limites externos podem mudar; quando forem derivados de
uma fonte oficial, documente a fonte e a data de verificação. Limites internos
devem ser fáceis de localizar, ter mensagem clara e possuir testes de fronteira,
sem duplicar o mesmo valor desnecessariamente em vários módulos.

## Organização do código

- mantenha regras reutilizáveis fora das rotas;
- deixe a fronteira de transação explícita no caso de uso que grava dados;
- evite dependências da aplicação em `app/core/` quando uma função pura resolve;
- prefira código direto a camadas genéricas sem uso concreto;
- preserve compatibilidade apenas quando há consumidor ou URL ainda suportado.

Essas orientações ajudam a revisão, mas não substituem julgamento técnico. Uma
exceção simples e bem explicada é preferível a uma abstração criada somente para
obedecer à estrutura atual.
