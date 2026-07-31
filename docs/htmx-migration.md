# Migra\u00e7\u00e3o para htmx

## Decis\u00e3o

A interface usa htmx 2.0.10, distribu\u00eddo localmente em
`app/static/vendor/htmx-2.0.10.min.js`. A vers\u00e3o \u00e9 fixa e o asset faz
parte do cache-busting da aplica\u00e7\u00e3o. N\u00e3o h\u00e1 depend\u00eancia de CDN: a CSP
continua com `script-src 'self'`.

As rotas completas permanecem a fonte de verdade e funcionam sem JavaScript.
Quando uma mesma URL recebe `HX-Request: true`, ela responde somente o
fragmento solicitado e inclui `Vary: HX-Request`. Isso evita que caches
misturem um fragmento com um documento completo. N\u00e3o h\u00e1 `hx-boost` global.

## Contratos

- Um fragmento tem um \u00fanico elemento raiz com `id` est\u00e1vel, que \u00e9 o alvo do
  swap.
- Escritas conservam CSRF. Navega\u00e7\u00e3o normal usa PRG; uma escrita htmx retorna
  `200` com o fragmento atualizado e feedback acess\u00edvel.
- Pr\u00e9vias de aposta s\u00e3o leituras e usam `hx-sync` para descartar respostas
  obsoletas.
- Um fechamento mostra no m\u00e1ximo 200 jogos, mas a grava\u00e7\u00e3o envia apenas as
  dezenas-base e recalcula todas as combina\u00e7\u00f5es no servidor.

## Rollback

Cada tela conserva sua URL e submiss\u00e3o HTML normal. Desabilitar ou remover o
script htmx restaura a navega\u00e7\u00e3o e os POSTs completos sem alterar dados ou
migra\u00e7\u00f5es. Os endpoints JSON legados s\u00e3o mantidos durante a transi\u00e7\u00e3o para
consumidores externos identificados.

## Valida\u00e7\u00e3o de implanta\u00e7\u00e3o

O Compose comum de desenvolvimento usa o servidor Flask e bind mount. A
valida\u00e7\u00e3o de produ\u00e7\u00e3o sempre usa `docker compose -f compose.yaml`, que
constr\u00f3i o est\u00e1gio `runtime` e executa Gunicorn. A grava\u00e7\u00e3o de um fechamento
de 20 dezenas deve ser medida nesse ambiente antes de qualquer libera\u00e7\u00e3o.
