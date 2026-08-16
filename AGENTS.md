# MegaSena — orientações de trabalho

## Escopo e fontes de verdade

Aplicação Flask local para importar resultados da Mega-Sena, consultar
estatísticas e organizar apostas. Frequências, filtros e relatórios descrevem
somente os concursos carregados: não são previsão nem aumentam a probabilidade
de uma combinação.

Antes de mudar comportamento, consulte nesta ordem o código, as migrações e os
testes afetados, e depois os documentos vivos:

- `README.md`: instalação, acesso e operação;
- `docs/business-rules.md`: contrato visível de concursos, apostas e fechamentos;
- `docs/architecture.md`: limites entre interface, serviços e persistência;
- `docs/development.md`: ciclo de desenvolvimento, schema e validação;
- `migrations/README`: estado e procedimento das migrações.

Atualize o documento que representa o contrato alterado na mesma mudança. Não
registre tentativas ou incidentes resolvidos em documentação operacional; use
um ADR quando uma decisão arquitetural tiver alternativas, impacto duradouro ou
plano de migração/rollback.

## Arquitetura e invariantes essenciais

O monólito modular organiza `app/web` (HTTP), `app/bets`, `app/draws`,
`app/settings` e `app/accounts` (casos de uso) sobre SQLAlchemy/PostgreSQL.
Regras reutilizáveis ficam fora das rotas e a transação cobre todo o caso de uso
que grava dados. Não acrescente camadas sem reduzir complexidade concreta.

PostgreSQL é o único backend operacional. `create_app()` não consulta banco,
não aplica migrações e não cria seed. `flask db upgrade` é etapa controlada:
o `docker-entrypoint.sh` a executa antes do servidor no Compose. Banco novo
pode permanecer sem linhas de configuração, pois a aplicação lê os padrões até
a primeira gravação. Mudança persistente exige revisão Alembic nova; não
reescreva uma revisão já aplicável nem use `stamp` ou `create_all()` como
bootstrap.

As `CHECK constraints` de `Draw` protegem valores derivados das dezenas. Não
duplique essa garantia com reparo silencioso em Python. Importações de XLSX são
atômicas e preservam os limites contra corrupção e consumo excessivo de
recursos. Apostas somente são gravadas após confirmação; normalização,
deduplicação, identificação do lote e gravação composta permanecem no servidor.

## Interface, segurança e exposição

O padrão atual é HTML renderizado no servidor e HTMX para atualizações
incrementais, com `Vary: HX-Request` quando a mesma rota devolve página ou
fragmento. JavaScript próprio não deve duplicar regras de negócio nem renderizar
dados que o servidor já fornece. Esse padrão é preferido por reduzir formatos e
consumidores paralelos; não é uma proibição absoluta de JSON. Uma API ou um
fluxo JavaScript adicional só é aceitável para consumidor identificado, contrato
documentado, autorização/CSRF preservados e testes proporcionais; atualize todos
os consumidores na mesma mudança.

Toda rota nasce protegida por sessão, exceto a lista pública explícita em
`PUBLIC_ENDPOINTS`. Escritas exigem CSRF. Preserve CSP, limites de upload e
requisição, hosts confiáveis e cookies `HttpOnly`/`SameSite`; `SECRET_KEY` é
obrigatória e não tem fallback. O sistema autentica, mas não particiona dados:
qualquer conta autenticada acessa o acervo comum. Não introduza propriedade de
dados ou papéis como efeito colateral de uma refatoração.

No Compose, a senha PostgreSQL e a chave de sessão são arquivos Docker secrets
em `.secrets/`, apontados por `DB_PASSWORD_FILE` e `SECRET_KEY_FILE`. O
provisionamento é `scripts/provision_secrets.ps1`: não imprima os valores, não
versione a pasta e trate `-Force` como rotação coordenada.

O Compose publica serviços apenas em loopback. Exposição externa requer HTTPS,
`FORCE_HTTPS`, revisão de hosts confiáveis, segredo estável e estratégia de
proxy. A imagem `runtime` usa gunicorn e usuário não-root; o override local só
monta código para desenvolvimento.

## Operação, riscos e validação

Use Docker Compose; não dependa de Python, banco ou ferramentas do projeto no
host. Comandos atuais:

```powershell
docker compose --env-file .env.docker up --build -d
docker compose --env-file .env.docker --profile quality run --rm quality
```

O estágio `quality` executa Ruff e a suíte mínima de segurança/fumaça. Não há
suíte ampla, cobertura, análise estática de tipos ou `pip-audit` dentro da
imagem. O CI executa o Compose e esse estágio em mudanças para `main` e
semanalmente; CodeQL e Dependabot cobrem análise de código e dependências no
GitHub. Isso não dispensa a
validação proporcional: percorra manualmente o fluxo alterado. Mudanças de
autenticação, sessão, CSRF ou autorização executam o comando `quality`; mudanças
de Docker ou dependências também exigem rebuild e subida da pilha.

Antes de manutenção de dados ou schema, gere e confira backup com
`./scripts/backup_postgres.ps1`. Mudança de schema exige ainda bootstrap em
PostgreSQL vazio, pela baseline Alembic, e teste de upgrade/downgrade quando a
revisão os alterar. `docker compose down` preserva dados; `down -v` remove o
volume e só cabe com autorização explícita. Preserve alterações locais não
relacionadas e não imprima segredos.

## Evolução de versões e compatibilidade

Mantenha dependências em faixas limitadas e atualize-as deliberadamente. Para
atualização mínima/patch, execute a validação proporcional e registre impacto
na documentação quando houver. Para mudança de versão menor ou maior, confirme
compatibilidade com Python, PostgreSQL, Flask e o contrato de implantação;
reconstrua a imagem do zero e execute `quality`. Quebras de contrato, schema ou
interfaces exigem decisão explícita, migração/rollback, consumidores atualizados
e uma nova revisão Alembic quando houver persistência. Compatibilidade só é
mantida enquanto houver consumidor conhecido.
