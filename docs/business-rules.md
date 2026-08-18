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
HTTP defensivos. A aplicação nega por padrão: `_require_login` exige sessão em
toda requisição, e `PUBLIC_ENDPOINTS` é a lista curta e explícita do que fica
de fora (hoje só a tela de login e os estáticos). Não há, porém, dono de
dado — autenticar não é particionar: concursos, apostas e configurações são
um acervo único que qualquer usuário autenticado vê e altera por inteiro. Pelo
mesmo motivo não há papel de administrador: qualquer usuário autenticado
acessa `/usuarios` e pode criar contas, redefinir senha de outra pessoa e
ativar ou desativar qualquer usuário — as duas únicas restrições são não
poder desativar a própria conta nem o último usuário ativo, para não travar
o acesso de todo mundo. A senha mínima (`MIN_PASSWORD_LENGTH` em
`app/accounts/service.py`) é curta de propósito: o controle de acesso aqui é
"quem tem a URL e uma conta", não uma barreira contra força bruta — isso já
é coberto pelo rate limit do login. Expor o serviço em rede exige, além
disso, HTTPS e revisão de hosts confiáveis.

Após o login, o parâmetro `next` só aceita caminhos locais. URLs com esquema ou
host externo, barras invertidas e formas percent-encoded que possam ser
normalizadas para um host externo são ignoradas.
