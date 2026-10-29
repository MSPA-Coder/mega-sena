# Regras funcionais

Este documento descreve o comportamento atual visível para quem usa o sistema.

## Concursos e importação

- A importação recebe um arquivo `.xlsx` escolhido pelo usuário ou baixa a
  planilha pelo link HTTPS salvo em **Configurações**; nos dois casos lê a
  primeira planilha e não armazena o arquivo.
- Cada linha válida precisa ter um número de concurso e seis dezenas distintas
  entre 1 e 60.
- Linhas inválidas ou repetidas no mesmo arquivo são ignoradas.
- Um concurso novo é incluído; um concurso existente é atualizado quando os
  dados importados mudam.
- Data, ganhadores e valores de premiação são opcionais e dependem das colunas
  reconhecidas no arquivo. Quando uma dessas colunas estiver ausente, uma
  reimportação preserva o metadado já armazenado; uma coluna presente pode
  atualizá-lo, inclusive para zero ou vazio conforme o tipo do campo.
- Uma célula monetária não vazia precisa conter um valor válido e não negativo.
  Valor monetário malformado interrompe a importação inteira, sem substituir
  valores existentes por zero.
- Datas e quantidades de ganhadores não vazias também precisam ser válidas;
  conteúdo malformado interrompe a importação atomicamente. Células realmente
  vazias continuam representando ausência de data ou zero ganhadores.
- A gravação é transacional: uma falha não deixa parte do arquivo aplicada.

O upload e o download remoto são limitados a 10 MB e a importação a 10.000
linhas. O link configurado precisa usar HTTPS e apontar para servidor público.
O conteúdo interno do XLSX também é verificado quanto a criptografia, quantidade
de arquivos, tamanho descompactado e taxa de compressão. São proteções contra
arquivos corrompidos ou consumo excessivo de recursos, não regras da loteria.

## Estatísticas

O dashboard calcula seus indicadores somente com os concursos presentes no
banco. O usuário pode considerar todo o histórico importado ou um período
recente — os períodos disponíveis vão de "Todos" aos últimos 10 concursos.

O dashboard mostra: total de concursos e proporção com e sem acertadores;
acertadores de sena, quina e quadra; distribuição da quantidade de pares; maior
sequência consecutiva; distribuição por faixas de dezenas; as dez dezenas mais
e menos frequentes; e dois gráficos, frequência por dezena e frequência por
soma sorteada.

Todos são descrições da amostra carregada. Nenhum deles prevê o próximo
concurso.

## Geração de apostas

- Cada aposta gerada tem de 6 a 20 dezenas distintas entre 1 e 60.
- Uma geração solicita de 1 a 100 apostas.
- Critérios em branco ficam desativados.
- Os critérios disponíveis tratam de sequência consecutiva (de 1 a 6; em branco
  desativa), pares, soma, quantidade de faixas ocupadas e concentração em uma
  faixa.
- Para apostas com mais de seis dezenas, todas as combinações internas de seis
  dezenas precisam satisfazer os critérios escolhidos.
- Na geração aleatória de seis dezenas, a pessoa escolhe se combinações
  idênticas a concursos importados são descartadas. A exclusão vem ativada por
  padrão; um resultado anterior pode voltar a ocorrer.
- O gerador evita apostas excessivamente parecidas dentro do mesmo lote.
- Opcionalmente, prioriza cobertura: compara até oito candidatas válidas por
  aposta e favorece a que menos repete grupos de quatro dezenas do lote. É uma
  heurística, sem garantia de cobertura ótima. Essas opções não alteram o fechamento.

Filtros restritivos podem impedir que a quantidade solicitada seja alcançada.
Nesse caso, o sistema entrega as apostas encontradas e informa a redução, em vez
de continuar tentando indefinidamente: cada geração tem um orçamento de cerca
de 3 segundos. Cada processo do servidor roda no máximo duas gerações ao mesmo tempo; as
seguintes são recusadas na hora com a mensagem de aguardar, para que gerações
pesadas não ocupem todas as threads e o `/health` continue respondendo.

Valores fora dos limites, texto em campos numéricos e pares mínimo/máximo
contraditórios são recusados com erro 400 e uma mensagem visível. O servidor
não limita, inverte nem ignora silenciosamente um filtro enviado pelo usuário.
A prévia (`/bets/preview`), o racional e a gravação das configurações seguem a
mesma regra: o erro aparece na tela em vez de o valor ser trocado em silêncio.

Os parâmetros da URL representam o estado da tela. Sem parâmetros na URL, são
usados os valores salvos em **Configurações**.

## Fechamento

O fechamento recebe de 6 a 20 dezenas-base distintas e produz todas as
combinações de seis dezenas contidas no conjunto: `C(n, 6)`. Os filtros da
geração aleatória não são aplicados nesse modo.

Essa faixa acompanha a regra oficial, conforme o
[portal da Mega-Sena da CAIXA](https://loterias.caixa.gov.br/Paginas/Mega-Sena.aspx)
(consultado em 25 de julho de 2026). Um fechamento de 20 dezenas contém 38.760
combinações. Para manter a resposta utilizável, a tela mostra uma prévia das
primeiras 200; ao gravar, o servidor recalcula e persiste o fechamento completo.

## Relatório combinatório

O universo real de referência tem `C(60, 6) = 50.063.860` resultados possíveis
e equiprováveis. O relatório também conta quantas combinações permanecem após
os filtros, mas esse é um universo descritivo usado para explicar e controlar a
geração, não o denominador da probabilidade de um sorteio futuro.

Antes da geração, `C(quantidade, 6) × número de apostas` é apresentado apenas
como limite superior teórico: apostas diferentes podem ter combinações internas
em comum. Quando há apostas concretas e a união envolve até 250.000
combinações internas, o relatório a conta exatamente; acima disso, mantém só o
limite superior para não tornar a interface custosa. A probabilidade exata usa
sempre `C(60, 6)` como denominador. Filtros não tornam os resultados mantidos
mais prováveis em um sorteio futuro.

Para apostas concretas, a tela também conta os resultados distintos que dariam
ao menos quadra, quina ou sena em alguma aposta do lote. As faixas são
acumuladas, não somáveis. Até 250.000 resultados individuais são enumerados;
acima desse custo, ou se o fechamento exibido for apenas uma prévia parcial,
a contagem fica indisponível. A probabilidade é a contagem dividida por
`C(60, 6)` e pressupõe sorteios uniformes.

## Apostas gravadas

As apostas geradas só são persistidas depois da confirmação do usuário. A
confirmação usa um identificador próprio: repetir o mesmo envio por retry do
navegador ou por concorrência entre workers devolve o resultado já gravado.
Uma nova prévia representa nova intenção, mesmo com as mesmas dezenas e o mesmo
concurso. Reutilizar o identificador com conteúdo ou usuário diferente é recusado.
Ao gravar:

- dezenas são normalizadas;
- duplicatas do mesmo envio são removidas;
- as apostas recebem um identificador comum de geração e o concurso informado;
- o concurso sugerido é o maior concurso importado mais um, e pode ser alterado;
- ao importar resultados, apostas do mesmo concurso são conferidas; quadra,
  quina e sena geram aviso. No histórico, toda dezena acertada fica destacada,
  mesmo sem prêmio, e a quantidade de acertos aparece junto à aposta.
  A conferência acompanha correções em reimportações. As apostas que existiam
  antes desta mudança foram associadas ao concurso 3076;
- até 20 lotes recentes ficam disponíveis para consulta; a tela carrega no
  máximo as primeiras 200 apostas de cada lote para manter a resposta limitada.
  O lote completo continua persistido e o fechamento completo continua sendo
  recalculado no servidor.

Um lote pode conter no máximo `C(20, 6) = 38.760` apostas, correspondente ao
maior fechamento aceito pela interface. Gravar um fechamento envia somente as
dezenas-base: quantidade de dezenas, de apostas e filtros da tela não participam.

A lista de concursos pode ser filtrada por número do concurso, quantidade de
pares, maior sequência consecutiva e presença de acertador da Mega Sena, e tem
salto direto para uma página.

Na importação, valor monetário de texto com um único separador e exatamente três
dígitos depois (`1.234`, `1,234`) é recusado como ambíguo — pode ser mil
duzentos e trinta e quatro ou um vírgula duzentos e trinta e quatro. Valores
com centavos (`1.234,56`) e células numéricas não são afetados.

Cada aposta salva pode ser excluída individualmente, com confirmação. A
exclusão remove somente a aposta escolhida; concursos importados não são
afetados.

## Auditoria

O sistema registra ações relevantes de escrita e administração: gravação e
exclusão de apostas, importações, configurações, limpeza total de dados e
gestão de contas. Cada evento contém ator, ação, entidade, identificador quando
existir, instante, resultado e contexto mínimo (rota, IP e origem quando
aplicável). Senhas, tokens, conteúdo de arquivos e formulários completos não
entram na auditoria.

## Escopo de segurança

Operações que alteram dados exigem token CSRF, e as respostas recebem cabeçalhos
HTTP defensivos. A aplicação nega por padrão: `requer_login` exige sessão em
toda requisição, e `PUBLIC_ENDPOINTS` é a lista curta e explícita do que fica
de fora (tela de login, health check e estáticos). Não há, porém, dono de
dado — autenticar não é particionar: concursos, apostas e configurações são
um acervo único que qualquer usuário autenticado vê e altera por inteiro. Isso
não significa que toda operação administrativa seja aberta: `/usuarios` e
suas mutações exigem o papel `admin`; contas comuns usam o papel `operador`.
Administradores podem criar contas, redefinir senhas, alterar papéis e ativar
ou desativar usuários. O serviço impede remover o último administrador, deixar
o último administrador ativo desativado, desativar a própria conta ou deixar
zero usuários ativos. A migração de papéis atribui `admin` às contas legadas
para preservar o acesso existente; novos usuários são `operador` por padrão.
O primeiro usuário é criado como administrador pelo comando `criar-usuario`.
O nome de usuário aceita até 80 caracteres (tamanho da coluna); acima disso a
criação é recusada com mensagem. A senha mínima é definida por `MIN_PASSWORD_LENGTH` em
`app/accounts/service.py`. O limite de tentativas de login é local à memória de
cada processo, reinicia com ele e não coordena workers ou instâncias. No VPS,
o Nginx aplica ao `POST /login` um `limit_req` compartilhado, que é parte
obrigatória da proteção atual junto com HTTPS e hosts confiáveis. Outra
topologia exposta precisa de proteção de borda equivalente ou armazenamento
compartilhado para o limitador; o contador em memória não basta em produção.

O logout invalida o cookie de sessão emitido (não só o apaga no navegador): a
marca da sessão inclui uma época por usuário, que o logout incrementa. Uma cópia
do cookie deixa de valer, e as sessões abertas em outros aparelhos da mesma
conta também caem. Trocar a senha tem o mesmo efeito.

Após o login, o parâmetro `next` só aceita caminhos locais. URLs com esquema ou
host externo, barras invertidas e formas percent-encoded que possam ser
normalizadas para um host externo são ignoradas.
