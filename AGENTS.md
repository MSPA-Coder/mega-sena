# MegaSena — orientações de trabalho

> **A frota é este projeto, o ControleBancario e o ControleRendaVariavel.** Os
> três compartilham o `SharedAuth`, o mesmo formato de Compose e Dockerfile e o
> mesmo portão `quality`, e servem de referência uns aos outros. Divergir é
> permitido quando for uma escolha consciente: experimente num deles e, se der
> certo, leve aos outros.
>
> **O ConfortoTermico não está na frota** e segue trilha própria desde
> 07/09/2026: a arquitetura dele é livre, e diferença em relação a ele **não é
> débito**. O que ele preserva é o contrato operacional — VPS, `deploy.sh`,
> vigia, autocura, alerta, backup e `SharedAuth`. Ver o ADR 008 daquele
> repositório.

## Escopo e fontes de verdade

Aplicação Flask para importar resultados da Mega-Sena, consultar estatísticas e
organizar apostas. O uso é individual pelo mantenedor, em ambiente local e no
VPS documentado. Frequências, filtros e relatórios descrevem somente os
concursos carregados: não são previsão nem aumentam a probabilidade de uma
combinação.

Antes de mudar comportamento, consulte nesta ordem o código, as migrações e os
testes afetados, e depois os documentos vivos:

- `README.md`: finalidade, início rápido e índice;
- `docs/business-rules.md`: contrato visível de concursos, apostas e fechamentos;
- `docs/architecture.md`: limites entre interface, serviços e persistência;
- `docs/development.md`: ciclo de desenvolvimento, schema e validação;
- `docs/deployment-vps.md`: operação, dados, backup e implantação;
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
no Compose, o serviço `migrate` a executa com o papel administrativo antes do
`app`, que conecta com o papel restrito `mega_sena_app` (só DML, provisionado
pelo `db-provision`) e recusa conexão superusuária. Banco novo
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
fragmento. É uma preferência, porque reduz formatos e consumidores paralelos,
não uma proibição: uma API JSON ou um fluxo JavaScript novo pode entrar quando
fizer sentido, preservando autorização e CSRF, com testes proporcionais e com
os consumidores atualizados na mesma mudança. O cuidado que continua valendo é
não duplicar no JavaScript uma regra de negócio que já vive no servidor.

Toda rota nasce protegida por sessão, exceto a lista pública explícita em
`PUBLIC_ENDPOINTS`. Escritas exigem CSRF. Preserve CSP, limites de upload e
requisição, hosts confiáveis e cookies `HttpOnly`/`SameSite`; `SECRET_KEY` é
obrigatória e não tem fallback. Sessão, CSRF, limite de tentativas de login,
controle de acesso, hash de senha, senha temporária e trava de troca
pendente, destino pós-login seguro e a marca que amarra a sessão à senha em
vigor, cabeçalhos de segurança e CSP, formatação
de números em pt-BR e a rota `/health` vêm de
[SharedAuth](https://github.com/MSPA-Coder/SharedAuth), biblioteca
compartilhada com os outros apps do mantenedor (ver README.md);
o padrão é usar a biblioteca. `core/security.py` e `core/formatting.py` são
adaptadores finos sobre ela; uma variação pode nascer aqui para experimentar e,
se servir aos outros, sobe para a biblioteca com tag nova. O sistema autentica,
mas não particiona dados:
qualquer conta autenticada acessa o acervo comum. A gestão de contas é uma
exceção administrativa deliberada: `/usuarios` exige `admin`, enquanto novos
usuários recebem `operador` por padrão; isso não introduz propriedade de dados.
A decisão de acervo comum, a alternativa recusada e o gatilho para revisá-la
estão registrados em
[ADR 0002](docs/adr/0002-acervo-comum-sem-dono.md).

No Compose, a senha PostgreSQL e a chave de sessão são arquivos Docker secrets
em `.secrets/`, apontados por `DB_PASSWORD_FILE` e `SECRET_KEY_FILE`. O
provisionamento é `scripts/provision_secrets.ps1`: não imprima os valores, não
versione a pasta e trate `-Force` como rotação coordenada.

O Compose publica serviços apenas em loopback. Exposição externa requer HTTPS,
`FORCE_HTTPS`, revisão de hosts confiáveis, segredo estável e estratégia de
proxy. A imagem `runtime` usa gunicorn e usuário não-root. O modo padrão
reconstrói sem cache a partir das tags base móveis em cada subida; inclua
`compose.dev.yaml` explicitamente para montar código durante desenvolvimento.

## Operação, riscos e validação

Use Docker Compose para validar a imagem e o Linux; não instale dependências do
projeto no Python global do host. Comandos atuais:

```powershell
docker compose --env-file .env.docker -f compose.yaml up --build -d
docker compose --env-file .env.docker -f compose.yaml --profile quality run --build --rm quality
```

`--build` mantém a validação explícita e reproduzível: o serviço `quality` não
monta o código do host, e Compose reconstrói sem cache com as tags base atuais
antes de executar os testes.

O `.venv` do projeto é runtime-only, criado com `uv sync --locked --python
3.15`. Lint, testes, banco e auditoria rodam nos serviços Compose. `sharedauth`
é instalado do GitHub na tag declarada em `pyproject.toml` e no commit
registrado em `uv.lock`.

O que merece teste, em que camada e em que forma está em `docs/TESTES.md`,
comum aos repositórios; leia antes de escrever ou remover um teste. Diante de
vermelho, decida de quem é o defeito antes de mexer: teste que mede texto
literal reprova mudança legítima, e nesse caso quem se corrige é a asserção.
Nunca escreva código para o teste passar.

O estágio `quality` executa Ruff e toda a suíte pytest, incluindo os contratos
de domínio de geração, fechamento e importação. O CI executa o Compose e esse
estágio em mudanças para `main` e semanalmente, audita as dependências Python
instaladas com `pip-audit` e a imagem servida com Trivy. O Dependabot cobre
dependências Python, imagens Docker e GitHub Actions. O CodeQL roda em
configuração padrão (Python e Actions, semanal) e é status check obrigatório no
ruleset do `main`, ao lado de `Qualidade`. O mypy estrito no `quality` cobre
números/critérios, contexto e resultados/comando de confirmação. O escopo
explícito em `pyproject.toml` cresce por fronteira, sem ignores em massa.
Isso não dispensa a validação proporcional:
percorra manualmente o fluxo alterado. Mudanças de
autenticação, sessão, CSRF ou autorização executam o comando `quality`; mudanças
de Docker ou dependências também exigem rebuild e subida da pilha.

Antes de manutenção de dados ou schema, gere e confira backup pelo
BackupRestore, projeto irmão (`python cli.py backup --projeto mega_sena
--tipos banco`); ele centraliza dump, catálogo e verificação dos quatro
projetos mantidos por ele, e este repositório não tem rotina própria. Mudança de
schema exige ainda bootstrap em
PostgreSQL vazio, pela cadeia Alembic, e teste de upgrade/downgrade quando a
revisão os alterar. `docker compose down` preserva dados; `down -v` remove o
volume e só cabe com autorização explícita. Preserve alterações locais não
relacionadas e não imprima segredos.

## Implantação em produção

Produção usa `compose.release.yaml`, imagens por digest de run verde de main,
com revisão/run e arquitetura conferidos antes do fast-forward. Não reconstrua
no VPS; use `~/deploy.sh megasena`. O CI ARM64 valida a mesma candidata em
qualidade, Chromium, scanners e Runtime contracts, e publica só após os gates.
Ver ADR 0003 e docs/deployment-vps.md. O Compose base mantém o build local.

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

**Faixas de dependência: mantenha o piso.** O Dependabot roda com
`versioning-strategy: increase-if-necessary`, a estratégia aceita para o
ecossistema `uv`: só eleva o requisito declarado quando isso for indispensável
à atualização. O piso registra a compatibilidade mínima efetivamente
verificada, não a versão mais nova disponível: elevá-lo declara uma
incompatibilidade que ninguém comprovou. A versão instalada é a do `uv.lock`:
depois de mudar uma faixa, rode `uv lock` e commite o resultado. O Dependabot
acompanha o lock pelo ecossistema `uv`.

Mantenha dependências em faixas limitadas e atualize-as deliberadamente. Para
atualização mínima/patch, execute a validação proporcional e registre impacto
na documentação quando houver. Para mudança de versão menor ou maior, confirme
compatibilidade com Python, PostgreSQL, Flask e o contrato de implantação;
reconstrua a imagem do zero e execute `quality`. Quebras de contrato, schema ou
interfaces exigem decisão explícita, migração/rollback, consumidores atualizados
e uma nova revisão Alembic quando houver persistência. Compatibilidade só é
mantida enquanto houver consumidor conhecido.

## Barreiras de segurança no CI

Duas verificações reprovam o PR e respondem perguntas diferentes:

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

Invariantes operacionais dessas verificações:

1. **O Trivy roda como contêiner, não como action de marketplace.** A política
   destes repositórios é `allowed_actions: selected` com apenas
   `github_owned_allowed` — action de terceiro é barrada antes de o workflow
   rodar, e o sintoma é `startup_failure` sem log nenhum. Não troque por uma
   action "porque é mais limpo".
2. **A varredura usa `docker save` + `--input`, sem montar
   `/var/run/docker.sock`.** Montar o socket daria ao scanner controle
   equivalente a root sobre o host; a leitura da imagem exportada evita essa
   concessão.
3. **O serviço servido declara `image:` com nome fixo no `compose.yaml`.** Sem
   isso o Compose batiza a imagem pelo nome do diretório, que muda conforme
   onde o repositório foi clonado — e a varredura fica sem alvo estável.
