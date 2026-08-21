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
obrigatória e não tem fallback. Sessão, CSRF, limite de tentativas de login,
controle de acesso, hash de senha, cabeçalhos de segurança e CSP, formatação
de números em pt-BR e a rota `/health` vêm de
[SharedAuth](https://github.com/MSPA-Coder/SharedAuth), biblioteca
compartilhada com os outros apps do mantenedor (ver README.md);
não reimplemente esse mecanismo localmente. `core/security.py` e
`core/formatting.py` são adaptadores finos sobre ela: mudança de
comportamento sobe para a biblioteca, com tag nova, não para cá. O sistema autentica, mas não particiona dados:
qualquer conta autenticada acessa o acervo comum. Não introduza propriedade de
dados ou papéis como efeito colateral de uma refatoração.

No Compose, a senha PostgreSQL e a chave de sessão são arquivos Docker secrets
em `.secrets/`, apontados por `DB_PASSWORD_FILE` e `SECRET_KEY_FILE`. O
provisionamento é `scripts/provision_secrets.ps1`: não imprima os valores, não
versione a pasta e trate `-Force` como rotação coordenada.

O Compose publica serviços apenas em loopback. Exposição externa requer HTTPS,
`FORCE_HTTPS`, revisão de hosts confiáveis, segredo estável e estratégia de
proxy. A imagem `runtime` usa gunicorn e usuário não-root. O modo padrão é
imutável, com somente `compose.yaml`; inclua `compose.dev.yaml` explicitamente
para montar código durante desenvolvimento.

## Operação, riscos e validação

Use Docker Compose; não dependa de Python, banco ou ferramentas do projeto no
host. Comandos atuais:

```powershell
docker compose --env-file .env.docker -f compose.yaml up --build -d
docker compose --env-file .env.docker -f compose.yaml --profile quality run --rm quality
```

O estágio `quality` executa Ruff e a suíte mínima de segurança/fumaça. Não há
suíte ampla, cobertura, análise estática de tipos ou `pip-audit` dentro da
imagem. O CI executa o Compose e esse estágio em mudanças para `main` e
semanalmente; o Dependabot cobre dependências Python, imagens Docker e GitHub
Actions. Não há varredura de código de segurança (CodeQL) neste projeto. Isso
não dispensa a validação proporcional: percorra manualmente o fluxo alterado. Mudanças de
autenticação, sessão, CSRF ou autorização executam o comando `quality`; mudanças
de Docker ou dependências também exigem rebuild e subida da pilha.

Antes de manutenção de dados ou schema, gere e confira backup pelo
BackupRestore, projeto irmão (`python cli.py backup --projeto mega_sena
--tipos banco`); ele centraliza dump, catálogo e verificação dos quatro
projetos, e este repositório não tem rotina própria. Mudança de schema exige
ainda bootstrap em
PostgreSQL vazio, pela baseline Alembic, e teste de upgrade/downgrade quando a
revisão os alterar. `docker compose down` preserva dados; `down -v` remove o
volume e só cabe com autorização explícita. Preserve alterações locais não
relacionadas e não imprima segredos.

## Implantação em produção

O sistema roda em um VPS Oracle atrás de Nginx com TLS, em
`https://megasena-mspa.duckdns.org`, a partir de `/home/ubuntu/apps/mega-sena`.

O código do servidor é espelho do `main`, em sentido único: desenvolvimento na
máquina local, commit, push ao GitHub, e só então implantação. **Não edite
código, não commite e não faça merge no VPS** — `~/deploy.sh megasena` aborta ao
encontrar árvore suja, e a *deploy key* do servidor é somente leitura, então um
push de lá falharia de qualquer forma.

`.secrets/` e `.certs/` não são versionados e vivem apenas no servidor; um
reclone precisa restaurá-los, ou o build falha e o banco fica inacessível. Os
dados ficam no volume `mega-sena_postgres_data`, fora da pasta do código:
substituir o diretório do projeto não os afeta. Consulte
`docs/deployment-vps.md` antes de qualquer operação no VPS.

## Evolução de versões e compatibilidade

**Faixas de dependência: alargue o teto, mantenha o piso.** O Dependabot roda
com `versioning-strategy: widen`. Quando ele propuser elevar o mínimo, aproveite
apenas a parte que alarga o teto e recuse a que sobe o piso. O piso registra a
compatibilidade mínima efetivamente verificada, não a versão mais nova
disponível: elevá-lo declara uma incompatibilidade que ninguém comprovou e não
muda nada do que é instalado, porque o pip já resolve para a versão mais nova
permitida pela faixa.


Mantenha dependências em faixas limitadas e atualize-as deliberadamente. Para
atualização mínima/patch, execute a validação proporcional e registre impacto
na documentação quando houver. Para mudança de versão menor ou maior, confirme
compatibilidade com Python, PostgreSQL, Flask e o contrato de implantação;
reconstrua a imagem do zero e execute `quality`. Quebras de contrato, schema ou
interfaces exigem decisão explícita, migração/rollback, consumidores atualizados
e uma nova revisão Alembic quando houver persistência. Compatibilidade só é
mantida enquanto houver consumidor conhecido.

## Barreiras de segurança no CI (desde 2026-08-21)

Duas verificações novas reprovam o PR, e as duas respondem perguntas
diferentes:

- **`pip-audit`** roda dentro da imagem `quality` e pergunta se alguma
  dependência Python *instalada* tem CVE conhecido. Auditar o ambiente
  instalado, e não o arquivo de requisitos, é o que responde sobre o que está
  rodando em vez do que está escrito.
- **Trivy** varre a imagem *servida* e cobre o que o `pip-audit` não vê: os
  pacotes do sistema operacional da imagem base.

Se uma delas reprovar, o conserto é atualizar a dependência ou a base — não
afrouxar a verificação. Vulnerabilidade sem correção publicada já é filtrada
(`--ignore-unfixed` no Trivy); no `pip-audit`, a saída é `--ignore-vuln <ID>`
com um comentário dizendo por quê, para cada exceção ser uma decisão explícita
e datada em vez de um vermelho permanente que se aprende a ignorar.

Três coisas que parecem detalhe e não são:

1. **O Trivy roda como contêiner, não como action de marketplace.** A política
   destes repositórios é `allowed_actions: selected` com apenas
   `github_owned_allowed` — action de terceiro é barrada antes de o workflow
   rodar, e o sintoma é `startup_failure` sem log nenhum. Não troque por uma
   action "porque é mais limpo".
2. **A varredura usa `docker save` + `--input`, sem montar
   `/var/run/docker.sock`.** Montar o socket é dar root na prática. Foi o
   motivo de o `autoheal` ter sido recusado no VPS, e vale igual aqui.
3. **O serviço servido declara `image:` com nome fixo no `compose.yaml`.** Sem
   isso o Compose batiza a imagem pelo nome do diretório, que muda conforme
   onde o repositório foi clonado — e a varredura fica sem alvo estável.
