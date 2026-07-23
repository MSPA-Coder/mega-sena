# Regras funcionais

Este documento descreve o comportamento atual que é relevante para quem usa o
sistema. Detalhes de implementação, decisões temporárias de refatoração e
contratos entre arquivos pertencem à documentação de arquitetura ou ao código.

## Concursos e importação

- A importação recebe uma planilha `.xlsx` e lê a primeira aba.
- Cada linha válida precisa identificar o concurso e seis dezenas distintas
  entre 1 e 60.
- Linhas inválidas ou repetidas no mesmo arquivo são ignoradas.
- Um concurso ainda inexistente é incluído; um concurso existente é atualizado
  quando os dados da planilha mudam.
- Datas, ganhadores e premiações são importados quando as colunas correspondentes
  estão disponíveis.
- Uma falha durante a gravação não deixa a importação parcialmente aplicada.

O upload e o conteúdo descompactado têm limites defensivos para evitar consumo
excessivo de memória ou arquivos XLSX malformados. Esses valores são proteções
operacionais, não regras da loteria.

## Estatísticas

O dashboard usa somente os concursos presentes no banco. O período pode abranger
todo o histórico importado ou os concursos mais recentes. Frequência, atraso,
paridade, soma, sequências e premiações descrevem essa amostra; não são previsão
do próximo resultado.

## Geração de apostas

- A aplicação aceita atualmente de 6 a 15 dezenas por aposta e de 1 a 100
  apostas por geração.
- Critérios em branco ficam desativados.
- Os critérios disponíveis controlam sequência consecutiva, quantidade de pares,
  intervalo da soma, faixas ocupadas e concentração por faixa de dezenas.
- Uma aposta de mais de seis dezenas só é aceita quando todas as combinações de
  seis dezenas que ela cobre atendem aos critérios informados.
- Na geração de seis dezenas, uma combinação igual a um resultado importado é
  descartada.
- O gerador procura diversidade dentro do mesmo lote. Com critérios muito
  restritivos, pode devolver menos apostas do que a quantidade solicitada.

Os parâmetros exibidos na URL representam o estado atual da tela e permitem
compartilhar ou reabrir a seleção. Quando a URL não informa parâmetros, a tela
usa os valores definidos em **Configurações**.

## Fechamento

O fechamento recebe atualmente entre 6 e 15 dezenas distintas, todas entre 1 e
60. Ele gera todas as combinações de seis dezenas contidas no conjunto, ou seja,
`C(n, 6)` apostas. Nesse modo, os filtros da geração aleatória não são aplicados.

Como o número de combinações cresce rapidamente, 15 é um limite operacional do
aplicativo. Ele não deve ser interpretado como o máximo oficial permitido pela
Mega-Sena.

## Relatório combinatório

O universo de referência contém `C(60, 6) = 50.063.860` resultados possíveis.
O relatório mostra quantas combinações permanecem após cada filtro e quantas são
cobertas pelas apostas selecionadas. A chance exibida é uma relação matemática
dentro desse universo filtrado; filtros baseados no histórico não tornam um
resultado futuro mais provável.

## Apostas gravadas

As apostas só são persistidas depois da confirmação do usuário. Ao gravar:

- dezenas são normalizadas e apostas repetidas no mesmo envio são removidas;
- as apostas recebem um identificador comum de geração;
- os lotes recentes podem ser consultados na tela de apostas.

## Escopo de segurança

Operações que alteram dados exigem token CSRF, e respostas recebem cabeçalhos
HTTP defensivos. O produto não possui autenticação porque seu escopo atual é o
uso local e individual. Expor o serviço em rede exige rever esse pressuposto,
além da configuração e do servidor de execução.
