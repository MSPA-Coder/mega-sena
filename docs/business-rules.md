# Regras funcionais

Este documento descreve o comportamento atual visível para quem usa o sistema.

## Concursos e importação

- A importação recebe um arquivo `.xlsx` e lê a primeira planilha.
- Cada linha válida precisa ter um número de concurso e seis dezenas distintas
  entre 1 e 60.
- Linhas inválidas ou repetidas no mesmo arquivo são ignoradas.
- Um concurso novo é incluído; um concurso existente é atualizado quando os
  dados importados mudam.
- Data, ganhadores e valores de premiação são opcionais e dependem das colunas
  reconhecidas no arquivo.
- A gravação é transacional: uma falha não deixa parte do arquivo aplicada.

O upload é limitado a 10 MB e a importação a 10.000 linhas. O conteúdo interno
do XLSX também é verificado quanto a criptografia, quantidade de arquivos,
tamanho descompactado e taxa de compressão. São proteções contra arquivos
corrompidos ou consumo excessivo de recursos, não regras da loteria.

## Estatísticas

O dashboard calcula seus indicadores somente com os concursos presentes no
banco. O usuário pode considerar todo o histórico importado ou um período
recente.

Frequência, atraso, soma, paridade, sequências e premiações são descrições dessa
amostra. Nenhum desses indicadores prevê o próximo concurso.

## Geração de apostas

- Cada aposta gerada tem de 6 a 20 dezenas distintas entre 1 e 60.
- Uma geração solicita de 1 a 100 apostas.
- Critérios em branco ficam desativados.
- Os critérios disponíveis tratam de sequência consecutiva, pares, soma,
  quantidade de faixas ocupadas e concentração em uma faixa.
- Para apostas com mais de seis dezenas, todas as combinações internas de seis
  dezenas precisam satisfazer os critérios escolhidos.
- Uma combinação de seis dezenas idêntica a um concurso importado é descartada.
- O gerador evita apostas excessivamente parecidas dentro do mesmo lote.

Filtros restritivos podem impedir que a quantidade solicitada seja alcançada.
Nesse caso, o sistema entrega as apostas encontradas e informa a redução, em vez
de continuar tentando indefinidamente.

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

O universo de referência tem `C(60, 6) = 50.063.860` resultados possíveis. O
relatório conta quantas combinações permanecem após os filtros e estima quantas
são cobertas pelas apostas selecionadas.

A cobertura exibida é uma relação matemática no universo filtrado. Ela não
significa que os resultados mantidos pelos filtros sejam mais prováveis em um
sorteio futuro.

## Apostas gravadas

As apostas geradas só são persistidas depois da confirmação do usuário. Ao
gravar:

- dezenas são normalizadas;
- duplicatas do mesmo envio são removidas;
- as apostas recebem um identificador comum de geração;
- lotes recentes ficam disponíveis para consulta.

Um lote pode conter no máximo `C(20, 6) = 38.760` apostas, correspondente ao
maior fechamento aceito pela interface.

## Escopo de segurança

Operações que alteram dados exigem token CSRF, e as respostas recebem cabeçalhos
HTTP defensivos. Não há autenticação porque o produto foi desenhado para uso
local e individual. Expor o serviço em rede muda esse pressuposto e exige
controles adicionais.
