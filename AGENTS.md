# MegaSena — guia de trabalho

<!-- comum: início. Cópia de _manutencao/compartilhados/AGENTS-comum.md; mude lá e rode sincronizar.py --aplicar. -->
## Regras comuns aos repositórios

**O que espera o "sim" do mantenedor:** deploy ou publicação, qualquer ação no
VPS, e apagar dados, volumes ou backups (`docker compose down -v` inclusive).
Commit e push não esperam. Na dúvida sobre algo irreversível, pergunte; no
resto, decida e diga o que decidiu.

**Ciclo.** Altere, rode a verificação completa deste repositório (seção
"Validação"), commite direto no `main` quando o bloco de trabalho estiver
pronto e dê `git push`: sem PR, sem push forçado, sem rebase do `main`
publicado. A CI roda depois, só como aviso, mas vermelho no `main` se
investiga. O Dependabot chega por PR, com merge manual. Ao terminar, diga o que
rodou, o resultado e o que deixou de validar.

**Dados e segredos.** Os bancos desta máquina são de teste: não provam nada
sobre valores reais e não pedem backup. Segredos ficam fora do Git (`.secrets/`
ou configuração do usuário) e não aparecem em código, imagem, log, diff,
documento nem relatório.

**Dependências.** Alargue o teto e preserve o piso já verificado: elevar o piso
afirma uma incompatibilidade, e isso exige prova. Vulnerabilidade se corrige
atualizando; exceção só explícita, com motivo e data. Enquanto o Dependabot não
aceitar Python 3.15, ele não propõe atualização de `uv` e o grafo do GitHub fica
parado no lock de 13/10/2026: confira alerta pela versão travada no repositório
e atualize à mão (`uv lock --upgrade-package <pacote>`, onde há `uv.lock`)
quando o `pip-audit` ou o Trivy apontarem.

**Testes.** `docs/TESTES.md`, onde existe, diz o que testar e como. Diante de
vermelho, decida de quem é o defeito; nunca escreva código para um teste
passar. Não rode duas verificações do mesmo repositório ao mesmo tempo: a
segunda recria o ambiente de teste e derruba a primeira.

**Cópias.** Este bloco, `docs/TESTES.md` e os arquivos listados em
`_manutencao/compartilhados/sincronizar.py` são cópias: mude a canônica lá e
rode `python compartilhados/sincronizar.py --aplicar` no `_manutencao`.

**Este arquivo.** Guarde aqui só o que o código não diz: limites, decisões com
o motivo, armadilhas e comandos. Cada regra mora num lugar só: o que este bloco
ou `docs/` já dizem não se repete. História fica no `git log`; decisão com
alternativas vira ADR, e ADR superado ganha a linha "Substituído por"; detalhe
de implementação fica no código. Para acrescentar uma regra, retire ou funda
outra: `sincronizar.py` reprova este arquivo acima de 900 palavras fora deste
bloco.

**Deploy (o que roda no VPS).** Só com o "sim", a cada vez. `~/deploy.sh <app>`
no VPS1 leva o checkout ao `main`, monta a imagem no servidor, confere
`/health` e volta sozinho se falhar; a volta não desfaz migração nem dado. O
VPS só espelha o `main`: nada se edita lá. Imagem-base nova (correção do Debian
ou do Python) só quando ele pedir: testa na máquina e depois
`~/deploy.sh <app> --refresh`.

**Dados de produção.** Mudança destrutiva, migração que transforma dado ou
conversão começa por um dump novo, feito com `~/backup-db.sh --forcar` no VPS e
conferido no catálogo do BackupRestore. Dump feito à mão não tem `.sha256` e
reprova a sincronização.
<!-- comum: fim -->

## O sistema

Aplicação Flask para importar resultados da Mega-Sena, consultar estatísticas e
organizar apostas. Uso individual do mantenedor, local e no VPS
(`https://megasena-mspa.duckdns.org`, deploy `~/deploy.sh megasena`).
Frequências e filtros descrevem os concursos carregados: não são previsão, e a
interface não deve sugerir o contrário.

Faz parte da frota com o ControleBancario e o ControleRendaVariavel: mesmo
SharedAuth, mesmo formato de Compose e de `quality`. Divergir é permitido
quando for escolha consciente; o que der certo aqui pode ir para os outros.

Leia só o documento do assunto da mudança: `docs/business-rules.md`
(concursos, apostas, fechamentos), `docs/architecture.md` (camadas e
persistência), `docs/development.md` (ambiente, mypy, navegador),
`docs/deployment-vps.md` (VPS e dados), `docs/travas.md` (locks e o que os
cobre) e `docs/adr/` (decisões).

## Validação

```powershell
.\scripts\quality.ps1
```

Roda (passos em `scripts/quality.passos`) Ruff, mypy estrito e pytest contra um `postgres-teste` recriado vazio a
cada execução, o que também prova a cadeia inteira de migrações. Rode antes de
todo commit de código. O mypy cobre os arquivos de `tool.mypy.files` no
`pyproject.toml` e cresce por fronteira, sem ignore em massa.

- Mudança visível: suba a pilha e percorra a tela ou o fluxo alterado.
- Só documentação: `git diff --check` e
  `python ../_manutencao/compartilhados/sincronizar.py`.
- Docker ou dependência: também subir a pilha (`up --build -d`) e conferir
  `/health`.
- Autenticação, sessão, autorização, CSRF ou proxy: login, logout e uma
  operação mutante.
- Mudança persistente: `upgrade` e `downgrade` da revisão alterada.
- JS que afeta aposta ou confirmação: o runner de navegador de
  `compose.browser.yaml` (comandos em `docs/development.md`).

## Limites que o código não mostra sozinho

- A transação cobre o caso de uso inteiro que grava; regra reutilizável fica
  fora das rotas.
- `create_app()` não toca no banco. Migração é o serviço `migrate`, com papel
  administrativo; o `app` conecta como `mega_sena_app` (só DML) e recusa
  superusuário. Toda mudança persistente ganha revisão Alembic nova; revisão
  aplicável não se reescreve, e `stamp` ou `create_all()` não servem de
  bootstrap. Banco novo pode ficar sem linhas de configuração: a aplicação usa
  os padrões até a primeira gravação, então não crie seed para isso.
- Toda rota exige sessão, salvo a lista explícita `PUBLIC_ENDPOINTS`; escrita
  exige CSRF.
- As `CHECK constraints` de `Draw` garantem os valores derivados das dezenas:
  não duplique com reparo silencioso em Python.
- Aposta só é gravada depois da confirmação; normalização, deduplicação e
  gravação ficam no servidor. A importação de XLSX é atômica e mantém os
  limites de tamanho.
- Apostas, padrões de geração e tema são de cada conta, sem exceção para
  `admin`; concursos são comuns. `/usuarios`, o endereço da planilha e
  `/reset` exigem `admin`. O ADR 0004 diz por quê.
- HTML do servidor com HTMX (`Vary: HX-Request` quando a rota devolve página
  ou fragmento) é o padrão, não proibição: JSON ou JS novo pode entrar desde
  que não duplique regra que já vive no servidor.
- Sessão, CSRF, limite de login, senhas, cabeçalhos e CSP, formatação pt-BR e
  `/health` vêm do SharedAuth; `app/core/security.py` e
  `app/core/formatting.py` são adaptadores finos. A biblioteca vem do GitHub,
  na tag do `pyproject.toml` e no commit do `uv.lock`. Variação nasce aqui e,
  se servir aos outros, sobe para a biblioteca com tag nova.

## Armadilhas

- O dump de produção do bloco comum se confere com
  `python cli.py listar --projeto mega_sena_vps`, na pasta do BackupRestore;
  `backup --projeto mega_sena` copia só o banco local de testes.
- `.secrets/` (criado por `scripts/provision_secrets.ps1`; `-Force` é rotação
  coordenada) e `.certs/` vivem só onde rodam: um reclone no VPS
  (`/home/ubuntu/apps/mega-sena`) precisa restaurá-los, ou o build falha. Os
  dados ficam no volume `mega-sena_postgres_data`, fora da pasta do código.
- A CI roda o Trivy como contêiner, com `docker save` e `--input`: action de
  terceiro é barrada pela política do repositório (`startup_failure` sem log),
  e montar o socket Docker daria root ao scanner. Por isso o serviço servido
  mantém `image:` com nome fixo.
- Vulnerabilidade sem correção publicada: `--ignore-vuln <ID>` no `pip-audit`,
  com comentário e data. O Trivy já ignora o que não tem correção.
