# Base compartilhada de engenharia

<!-- SHARED-ENGINEERING-BASE:BEGIN version="1.2" -->

## Governança deste bloco-base

Este bloco estabelece as orientações compartilhadas e permanentes do mantenedor
para seus projetos Python e Flask.

Ele é controlado pelo mantenedor e não deve ser alterado, resumido, removido,
deslocado, enfraquecido ou substituído automaticamente durante implementação,
correção, refatoração, atualização de documentação ou manutenção ordinária.

Uma alteração neste bloco somente é autorizada quando o mantenedor solicitar
explicitamente, na conversa atual, uma mudança na **base compartilhada de
engenharia**. Um pedido genérico para melhorar, atualizar, organizar ou corrigir
o projeto não autoriza modificar este bloco.

Se uma tarefa entrar em conflito com estas orientações:

1. não reescreva a orientação conflitante;
2. explique objetivamente o conflito;
3. proponha a menor exceção necessária;
4. aguarde autorização explícita quando a exceção alterar segurança,
   integridade, persistência, produção ou confiabilidade;
5. registre a exceção na seção específica do projeto.

Arquivos `AGENTS.md` em subdiretórios podem acrescentar comandos e regras
locais, mas não devem enfraquecer esta base. Não crie nem altere
`AGENTS.override.md` sem autorização explícita do mantenedor.

Mudanças aprovadas nesta base devem:

- incrementar sua versão;
- registrar uma justificativa curta;
- ser propagadas deliberadamente aos projetos que usam a mesma base;
- preservar os marcadores de início e fim;
- atualizar a verificação automática de integridade, quando existente.

### Histórico de mudanças

- **1.2** — Exige bootstrap de bancos novos por revisões Alembic e adoção legada explícita e verificada.
- **1.1** — Acrescenta diretrizes para HTMX e explicita o desenvolvimento
  container-first, mantendo no host somente as ferramentas de orquestração.

A flexibilidade técnica prevista neste documento não autoriza o próprio agente a
apagar ou reescrever as orientações. Soluções alternativas devem ser
implementadas como decisões justificadas ou desvios aprovados, mantendo a base
legível e estável.

## Intenção e liberdade técnica

Os projetos usam Python e Flask, com PostgreSQL como único banco operacional e
Docker para empacotamento e implantação.

PostgreSQL também é o banco utilizado em todos os testes que exercem
persistência. Testes unitários de cálculos, validações e regras puras não usam
banco de dados. SQLite somente é permitido quando for o objeto explícito da
funcionalidade testada, como a leitura de uma base legada; não é usado para
simular PostgreSQL.

### Ambiente de desenvolvimento container-first

O host mantém somente Codex, Git, GitHub CLI, Docker Desktop, editor e os
componentes necessários à execução do Docker. Python, PostgreSQL, `psql`,
Node.js quando necessário, dependências, migrações, testes, lint, análise de
tipos, build e demais ferramentas do projeto são executados em contêineres.

- O projeto deve oferecer comandos Docker Compose reproduzíveis para iniciar a
  aplicação e o banco, aplicar migrações e executar testes e controles de
  qualidade.
- Não presuma que executáveis do projeto estejam instalados ou disponíveis no
  `PATH` do host.
- Uma ferramenta ausente deve ser incorporada à imagem ou ao serviço adequado,
  com versão controlada; não deve ser instalada no host como correção pontual.
- Use volumes e caches somente quando preservarem isolamento e
  reprodutibilidade, evitando arquivos do repositório pertencentes a `root`.
- Serviços de desenvolvimento e teste usam credenciais, redes, bancos e volumes
  separados da produção.
- O acesso ao daemon Docker equivale a acesso privilegiado ao host. Não monte o
  socket do Docker em contêineres nem use modo privilegiado sem necessidade
  concreta, avaliação de risco e autorização explícita.

Essas escolhas são a base atual, não uma proibição de evolução. Bibliotecas,
ferramentas, padrões ou componentes adicionais podem ser adotados quando
trouxerem benefício concreto de segurança, confiabilidade, desempenho,
simplicidade ou manutenção.

Toda divergência relevante deve registrar:

- problema concreto que pretende resolver;
- benefício esperado;
- impacto de compatibilidade;
- riscos e alternativas consideradas;
- estratégia de migração ou rollback;
- testes e validações aplicáveis.

Não transforme uma implementação existente em restrição permanente sem razão de
domínio, segurança, operação ou manutenção.

## Arquitetura proporcional

Use uma fábrica de aplicação e organize funcionalidades em módulos ou
blueprints. O fluxo de referência é:

```text
HTTP -> validação e normalização -> caso de uso -> persistência
```

Esse fluxo orienta responsabilidades, mas não obriga a existência de uma pasta
ou classe para cada camada.

- Rotas tratam HTTP, autenticação, autorização, entrada e resposta.
- Casos de uso ou serviços coordenam regras de negócio e limites transacionais.
- Persistência concentra acesso ao banco e consultas reutilizáveis.
- Templates apresentam dados; não concentram regras de negócio.
- Regras importantes devem ser testáveis sem uma requisição HTTP.
- Prefira composição a herança e funções simples para lógica sem estado.
- Use classes quando houver estado coerente, invariantes, ciclo de vida ou
  polimorfismo real.
- Não crie interfaces, repositories ou camadas vazias para satisfazer um
  desenho teórico.

Application Factory, Service Layer, Unit of Work, Repository, Adapter, Strategy,
Policy e Value Object são padrões disponíveis, não uma lista obrigatória. Adote
um padrão quando ele reduzir uma complexidade concreta ou proteger um contrato
importante.

## Persistência e integridade

PostgreSQL é a fonte de verdade do ambiente operacional e dos testes de
persistência.

- Represente dados estruturados e relacionamentos estáveis com colunas, tabelas
  e relações explícitas.
- Use `JSONB` para dados semiestruturados, atributos variáveis ou documentos
  externos cuja estrutura possa evoluir. Não o use apenas para evitar modelagem
  relacional.
- Proteja invariantes também no banco, quando aplicável, com `NOT NULL`,
  `UNIQUE`, `CHECK`, foreign keys e constraints apropriadas.
- Crie índices a partir das consultas e volumes esperados; não indexe
  mecanicamente todas as colunas.
- Índices GIN ou de expressão para `JSONB` devem corresponder a consultas reais
  e ter benefício verificável.
- Toda alteração persistente de schema usa uma nova revisão Alembic.
- Bancos novos são criados exclusivamente por `alembic upgrade head`; não use
  `create_all()` seguido de `stamp` como atalho de bootstrap operacional.
- A adoção de schema legado sem `alembic_version` é uma operação administrativa
  explícita, com verificação estrutural, backup validado e registro da revisão;
  ela não ocorre automaticamente no startup.
- Migrações autogeradas são candidatas e precisam de revisão manual.
- Não reescreva uma migração que possa ter sido aplicada em outro banco.
- Alterações destrutivas ou transformações de dados reais exigem backup
  validado, plano de migração e autorização explícita.
- Não mantenha adaptadores, condicionais ou tipos especiais apenas para
  compatibilidade com SQLite, salvo quando o produto possuir funcionalidade
  explícita de importação ou leitura desse formato.

## Transações, concorrência e efeitos externos

O caso de uso que inicia uma operação de escrita é responsável por seu limite
transacional. Camadas inferiores não fazem `commit` por conta própria.

- Uma operação composta deve concluir integralmente ou sofrer rollback integral.
- Validações que protegem integridade concorrente não devem existir apenas no
  código; use constraints, locks ou níveis de isolamento quando necessários.
- `Read Committed` é o padrão normal do PostgreSQL.
- Locks, controle otimista, `Repeatable Read` ou `Serializable` devem responder
  a uma condição de corrida identificada e possuir testes no PostgreSQL.
- Quando houver falha de serialização, o caso de uso deve poder repetir a
  transação completa com segurança.
- Não mantenha transações abertas durante chamadas externas lentas sem
  necessidade.
- Banco de dados, e-mail, APIs e dispositivos externos não formam uma única
  transação atômica.
- Quando a consistência com um sistema externo for crítica, considere
  idempotência, retentativas controladas, registro de estado ou padrão Outbox.
- Retentativas automáticas só são seguras para operações idempotentes ou
  protegidas contra duplicidade.

## Testes e qualidade

Use o teste mais rápido que ofereça confiança suficiente, sem substituir o banco
de produção por outro dialeto.

- Testes unitários de cálculos, normalização, validações e regras de domínio não
  usam banco.
- Dependências externas são substituídas por fakes ou adapters controlados
  quando o objetivo não for validar a própria integração.
- Testes de models, repositories, serviços com persistência e rotas que gravam
  dados usam PostgreSQL descartável.
- Migrações, constraints, transações, rollback, concorrência, locks, isolamento,
  `JSONB`, índices e consultas específicas são validados em PostgreSQL.
- A suíte nunca acessa o banco operacional.
- O schema de teste é criado com `alembic upgrade head`.
- `create_all()` somente pode ser usado quando o teste deliberadamente não
  avaliar migrações e isso não reduzir a confiança no schema.
- Cada teste deve ser isolado por rollback transacional, savepoint, schema ou
  banco próprio.
- Testes paralelos não compartilham estado mutável.
- Fixtures criam somente os dados necessários e não dependem da ordem de
  execução.
- Relógio, aleatoriedade, rede e serviços externos são controlados quando
  puderem tornar o teste não determinístico.
- Testes HTTP protegem autenticação, autorização, validação e contratos
  observáveis.
- Testes em navegador ficam reservados às jornadas críticas.
- Correções devem incluir um teste que demonstre a falha quando isso for viável.
- Teste comportamento e invariantes, não detalhes internos acidentais.
- Cobertura é uma rede de segurança, não um objetivo isolado.
- SQLite só aparece em testes de funcionalidades que realmente leem, importam ou
  transformam arquivos SQLite.

Para projetos novos, prefira pytest, Ruff, análise de tipos gradual com mypy ou
ferramenta equivalente, auditoria de dependências e CI. Suítes existentes em
`unittest` podem permanecer quando forem confiáveis; não as reescreva apenas
para uniformizar ferramentas.

## Estratégia de validação progressiva

A validação deve equilibrar retorno rápido durante o desenvolvimento e confiança
integral antes da conclusão.

Não execute automaticamente a suíte completa depois de cada pequena alteração.

### Ciclo de desenvolvimento

Durante a implementação:

1. identifique o comportamento, o risco e os consumidores afetados;
2. execute primeiro o menor teste que reproduza ou proteja esse comportamento;
3. depois de corrigido, execute os testes do módulo ou caso de uso relacionado;
4. quando houver persistência, execute os testes PostgreSQL correspondentes;
5. amplie a seleção quando a mudança afetar contratos compartilhados, segurança,
   arquitetura ou múltiplos consumidores.

Durante esse ciclo:

- use saída compacta, como `-q`, `-x` e `--tb=short`;
- interrompa na primeira falha quando isso acelerar o diagnóstico;
- use `--last-failed` apenas para corrigir falhas já conhecidas;
- não calcule cobertura repetidamente;
- não execute E2E, auditoria completa ou build de produção após cada edição;
- não repita uma validação cujo código e dependências relevantes não mudaram;
- mantenha registro dos comandos já executados durante a tarefa.

### Validação completa de encerramento

Quando a implementação estiver estável, execute uma única validação completa com
todos os controles aplicáveis ao projeto.

A validação final deve executar sem filtros parciais como caminhos específicos,
`-k`, `--last-failed` ou exclusões de testes lentos, salvo quando a própria
configuração oficial da suíte separar etapas complementares que também serão
executadas.

Conforme o projeto e o risco, a validação final inclui:

1. suíte unitária completa;
2. testes de integração com PostgreSQL;
3. testes de migração;
4. testes HTTP e E2E aplicáveis;
5. lint;
6. análise de tipos;
7. cobertura;
8. auditoria de dependências;
9. construção da imagem de produção;
10. smoke test da pilha Docker.

Qualquer alteração posterior em código, testes, migrations, dependências ou
configuração invalida a validação completa anterior. Nesse caso:

1. execute primeiro o teste que falhou ou foi afetado;
2. execute os testes relacionados;
3. quando o código voltar a ficar estável, repita a validação completa uma única
   vez.

Mudanças exclusivamente documentais não exigem a suíte completa, salvo quando a
documentação for validada ou consumida por testes, empacotamento ou automação.

### Otimização segura

- Reutilize um PostgreSQL descartável durante a mesma tarefa quando isso não
  comprometer isolamento.
- Aplique migrações novamente durante a iteração somente quando models ou
  revisions mudarem.
- Use rollback, savepoints, bancos ou schemas separados para manter testes
  independentes.
- Considere execução paralela somente depois que o isolamento entre workers
  estiver garantido.
- Meça periodicamente os testes mais lentos e corrija gargalos reais.
- Preserve uma execução completa em ambiente limpo na CI, mesmo quando a
  validação local já tiver sido concluída.
- Resultados bem-sucedidos devem ser apresentados de forma resumida; detalhes
  completos são necessários principalmente para falhas.

Ao concluir uma tarefa, informe:

- testes direcionados executados;
- validação final executada;
- resultado;
- controles omitidos e respectivos motivos.

## Segurança e interface

- Valide e normalize toda entrada nas fronteiras.
- A autorização é aplicada no servidor; menus e botões são apenas apresentação.
- Escritas originadas no navegador usam proteção CSRF.
- Preserve escape de HTML, CSP, cookies seguros, hosts confiáveis, limites de
  requisição e validação defensiva de uploads.
- Segredos nunca ficam no código, imagem, logs, mensagens de erro ou valores
  padrão de produção.
- Logs não expõem senhas, tokens, conteúdo financeiro ou dados pessoais
  desnecessários.
- APIs e respostas JSON possuem contratos coerentes; mudanças coordenam backend,
  consumidores, testes e documentação.
- HTML deve ser semântico e acessível.
- CSS e JavaScript permanecem em assets próprios quando a política de segurança
  impedir código inline.

### HTMX e interação orientada pelo servidor

HTMX pode ser adotado como mecanismo preferencial para interações incrementais
orientadas pelo servidor quando reduzir JavaScript próprio e preservar a
simplicidade do fluxo Flask e HTML.

- O servidor continua sendo a fonte de verdade. Atributos `hx-*`, estados da
  interface e respostas parciais não substituem validação, autenticação,
  autorização, CSRF, transações ou invariantes de domínio.
- `HX-Request` e demais cabeçalhos do cliente são sinais de negociação de
  apresentação, nunca prova de autorização ou origem confiável.
- Endpoints HTMX usam semântica HTTP coerente: operações seguras não alteram
  estado; escritas usam métodos adequados e proteção CSRF.
- Respostas parciais são produzidas por templates e componentes reutilizáveis,
  sem duplicar regras de negócio no navegador.
- Preserve HTML semântico, acessibilidade, foco, mensagens de erro, estados de
  carregamento e navegação/histórico quando a interação alterar conteúdo ou URL.
- Ofereça resposta completa ou degradação progressiva quando isso for viável e
  trouxer benefício concreto de robustez, acessibilidade ou testabilidade.
- JavaScript complementar fica em assets próprios e é reservado a comportamentos
  que HTMX e HTML não resolvam com clareza. Evite handlers inline quando forem
  incompatíveis com a CSP do projeto.
- Fixe a versão do HTMX. Prefira asset local versionado; quando usar CDN,
  autorize explicitamente a origem na CSP e use integridade do sub-recurso
  quando disponível. Nunca dependa de uma versão `latest` em produção.
- Testes HTTP cobrem tanto requisições normais quanto requisições HTMX nos
  fluxos em que a resposta ou o comportamento diferir.

## Produção e Docker

O artefato de produção é uma imagem construída e reproduzível.

- Use servidor WSGI apropriado; nunca o servidor de desenvolvimento do Flask.
- A imagem de produção contém somente código e dependências de runtime.
- Execute com usuário não-root e menor privilégio possível.
- Não monte o código-fonte do host no contêiner de produção.
- Dados persistentes ficam em volumes ou serviços próprios.
- Segredos são concedidos somente aos serviços que precisam deles,
  preferencialmente como arquivos.
- Preserve health checks, limites de logs, timeouts e desligamento gracioso.
- A aplicação só inicia depois que o banco estiver saudável e as migrações
  tiverem sido aplicadas por uma etapa controlada.
- Bind mounts, debugger e dependências de desenvolvimento pertencem ao Compose
  de desenvolvimento ou Dev Container.
- Use builds multi-stage quando eles reduzirem de forma útil o tamanho, as
  dependências ou a superfície de ataque.
- A infraestrutura de testes usa credenciais, volumes e bancos descartáveis
  separados da implantação operacional.

## Desempenho, confiabilidade e manutenção

- Meça antes de otimizar.
- Investigue paginação, N+1, plano de consulta e índices antes de adicionar
  cache.
- Cache exige política explícita de invalidação.
- Integrações externas usam Adapter e possuem timeout.
- Retentativas e circuit breaker são adicionados conforme o risco real.
- Falhas esperadas ficam observáveis e produzem mensagens seguras.
- Dependências devem ter faixas ou locks reproduzíveis e atualização deliberada.
- Prefira bibliotecas maduras quando elas reduzirem risco.
- Prefira a biblioteca padrão quando ela resolver o problema com clareza.
- Atualize código, testes, migrações e documentação como uma única mudança
  coerente.
- Preserve alterações locais não relacionadas.
- Informe toda validação que não pôde ser executada.

<!-- SHARED-ENGINEERING-BASE:END -->

# Orientações específicas do projeto

## Fonte de verdade e escopo

Este repositório é uma aplicação Flask para importar resultados da Mega-Sena,
consultar estatísticas e organizar apostas. Antes de alterar comportamento,
consulte:

- `docs/business-rules.md` para regras visíveis ao usuário;
- `docs/architecture.md` para limites arquiteturais;
- `docs/development.md` para desenvolvimento, testes e migrações;
- `README.md` para instalação e operação.

Frequências, filtros e relatórios descrevem somente o histórico carregado. Não
apresente estatísticas como previsão nem como aumento de probabilidade de uma
combinação.

## Persistência e implantação: invariantes a preservar

PostgreSQL é o único backend operacional. `create_app()` nunca aplica
migrações nem grava dados por conta própria — nenhuma consulta ao banco
acontece durante a construção da aplicação. `flask db upgrade` e
`flask seed-defaults` são etapas controladas e separadas, executadas por
`docker-entrypoint.sh` (Docker) ou manualmente (Python local) sempre antes de
iniciar o servidor. A suíte de testes usa PostgreSQL descartável para tudo que
toca persistência (`tests/support.py` cria o schema uma vez por processo via
Alembic e reseta cada teste por TRUNCATE); testes puros de critérios,
combinatória, normalização e estatísticas permanecem sem banco. A imagem de
produção (`Dockerfile`, estágio `runtime`) roda sob gunicorn, com usuário
não-root e sem bind mount; `compose.override.yaml` concentra bind mount e
ferramentas de desenvolvimento (estágio `dev`), mesclado automaticamente pelo
Docker Compose em ambiente de desenvolvimento.

Ao alterar áreas correspondentes, preserve essas propriedades — não as
reintroduza como atalho de conveniência (ex.: religar seed de dados dentro de
`create_app()`, voltar a usar SQLite para simular persistência em um teste
novo, ou aplicar migrações fora de uma etapa controlada). Execute
`scripts.verify_postgres` para mudanças de persistência.

## Arquitetura

O projeto é um monólito modular organizado por funcionalidade:

```text
navegador
    ↓
app/web
    ↓
app/bets | app/draws | app/settings
    ↓
SQLAlchemy
```

- `app.create_app()` é a fábrica da aplicação.
- `app/web` adapta HTTP e chama os casos de uso.
- `app/bets` concentra critérios, geração, fechamento e combinatória.
- `app/draws` concentra importação, consulta e estatísticas.
- `app/settings` concentra preferências e manutenção solicitada pelo usuário.
- `app/core` recebe apenas código realmente compartilhado.
- Regras reutilizáveis ficam fora das rotas.
- Transações abrangem o caso de uso completo que altera dados.

A estrutura atual é proporcional ao produto. Não adicione camadas vazias nem
reorganize módulos sem reduzir complexidade concreta.

## Regras funcionais duráveis

### Concursos e importação

- Cada linha válida possui número de concurso e seis dezenas distintas entre 1
  e 60.
- Linhas inválidas ou repetidas no mesmo arquivo são ignoradas.
- Concurso novo é incluído; concurso existente é atualizado quando os dados
  importados mudam.
- A importação é atômica: uma falha não deixa parte do arquivo aplicada.
- Preserve as proteções contra XLSX corrompido, criptografado ou criado para
  consumo excessivo de recursos.

### Geração e fechamento

- A interface aceita apostas de 6 a 20 dezenas distintas entre 1 e 60.
- Uma geração aleatória solicita de 1 a 100 apostas.
- Critérios em branco ficam desativados.
- Para apostas maiores que seis dezenas, todas as combinações internas de seis
  dezenas satisfazem os critérios ativos.
- O gerador possui limite de tentativas e informa quando não alcança a
  quantidade solicitada.
- O fechamento produz todas as combinações `C(n, 6)` das dezenas-base e não usa
  os filtros da geração aleatória.
- Um fechamento de 20 dezenas contém 38.760 combinações; a visualização pode ser
  limitada, mas a gravação deve recalcular o conjunto completo no servidor.
- A cobertura combinatória não representa maior probabilidade futura.

### Persistência de apostas

- Apostas só são persistidas após confirmação do usuário.
- Dezenas são normalizadas e duplicatas do mesmo envio são removidas.
- Apostas do mesmo lote compartilham um identificador de geração.
- Uma gravação composta é transacional.

## Segurança e exposição

- Operações mutáveis exigem CSRF.
- Preserve CSP, cookies `HttpOnly` e `SameSite`, hosts confiáveis e limites de
  upload e requisição.
- O produto atual foi desenhado para uso local e individual e não possui
  autenticação.
- Expor o serviço em rede muda o modelo de ameaça e exige controle de acesso,
  `SECRET_KEY` estável, HTTPS, revisão de hosts e configuração de proxy.
- Não reduza validações de arquivos ou limites de recursos para contornar um
  teste.

## Verificação específica

Use a estratégia progressiva da base. Os controles atuais incluem:

```powershell
python -m ruff check app migrations scripts tests run.py
python -m pytest -q
python scripts/audit_dependencies.py
docker compose --env-file .env.docker up -d
docker compose --env-file .env.docker exec app python -m scripts.verify_postgres
```

`pytest` já roda a suíte inteira contra um PostgreSQL descartável
(`TEST_DATABASE_URL`, ou `DATABASE_URL` como alternativa); não existe uma
suíte SQLite separada a considerar como sinal parcial. Ao tocar uma área de
banco, valide migrations, constraints e transações no PostgreSQL real.

Ao mudar critérios de geração, avalie os consumidores relevantes:

1. normalização e aceitação;
2. geração simples e múltipla;
3. relatório combinatório;
4. configurações persistidas;
5. formulário, URL e JavaScript;
6. testes proporcionais ao risco.

## Prática de mudança

- Limites externos citam fonte e data de verificação.
- Limites internos possuem justificativa de domínio, segurança, desempenho ou
  experiência do usuário.
- Preserve compatibilidade quando houver consumidor conhecido.
- Atualize regras funcionais, arquitetura e desenvolvimento quando seus
  contratos mudarem.
- Use UTF-8 e preserve alterações locais não relacionadas.
- Documente o estado atual, não o histórico de tentativas.

## Desvios aprovados da base compartilhada

Não há desvios aprovados nem lacunas conhecidas pendentes.
