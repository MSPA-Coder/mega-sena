# Interface HTMX

A interface usa htmx 2.0.10 distribuído localmente em
`app/static/vendor/htmx-2.0.10.min.js`. Não há dependência de CDN: a CSP mantém
`script-src 'self'`.

As páginas Jinja completas são a fonte de verdade e funcionam sem JavaScript.
Quando a mesma URL recebe `HX-Request: true`, ela responde somente o fragmento
solicitado e inclui `Vary: HX-Request`, evitando que caches misturem fragmentos
e documentos completos. Não há `hx-boost` global.

## Contratos da interface

- Cada fragmento tem um único elemento raiz e um `id` estável, usado como alvo
  de troca.
- Escritas mantêm CSRF. Formulários normais usam PRG; uma escrita HTMX retorna
  o fragmento atualizado e feedback acessível.
- Prévias de apostas são leituras e usam `hx-sync` para descartar respostas
  obsoletas.
- Um fechamento mostra no máximo 200 jogos, mas a confirmação envia somente as
  dezenas-base; o servidor recalcula e grava todas as combinações.
- Em `/api/combinations`, os campos legados `covered_by_amount` e
  `chance_with_amount_*` continuam disponíveis. `coverage_kind` informa se a
  cobertura é `exact` ou `theoretical_upper`; consumidores novos devem usar
  `single_bet_probability_*` para a probabilidade real de uma aposta.

Desabilitar o script HTMX preserva navegação e POSTs HTML normais, sem alterar
dados. A validação de produção usa `docker compose -f compose.yaml`, que monta
a imagem `runtime` com Gunicorn, usuário não-root e sem bind mount.
