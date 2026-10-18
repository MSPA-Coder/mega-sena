import assert from 'node:assert/strict';
import {test} from 'node:test';
import {chromium} from 'playwright';

const base = process.env.BASE_URL;
async function withPage(region, action) {
  const browser = await chromium.launch({headless: true});
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    await page.goto(base + '/login');
    await page.locator('[name=username]').fill('browser-' + region);
    await page.locator('[name=password]').fill('Synthetic-browser-only-2026!');
    await Promise.all([page.waitForURL('**/dashboard'), page.locator('button[type=submit]').click()]);
    await action(page);
  } catch (error) {
    await page.screenshot({path: '/results/mega-' + region + '-failure.png', fullPage: true});
    throw error;
  } finally { await browser.close(); }
}
async function state(page) {
  const response = await page.request.get(base + '/__browser__/state');
  assert.equal(response.status(), 200);
  return response.json();
}
test('gerar não grava; confirmar e repetir preservam lote e auditoria', async () => {
  await withPage('br', async page => {
    await page.goto(base + '/bets');
    const before = await state(page);
    await page.locator('#generation-amount').fill('2');
    await page.locator('#generate-bets').click();
    await page.locator('#generation-result [name=bet]').first().waitFor({state: 'attached'});
    assert.equal(await page.locator('#generation-result [name=bet]').count(), 2);
    assert.deepEqual(await state(page), before);
    const confirmation = await page.locator('#generation-result form').evaluate(form => [...new FormData(form)]);
    await page.getByRole('button', {name: 'Gravar no banco', exact: true}).click();
    await page.getByRole('dialog').getByRole('button', {name: 'Confirmar', exact: true}).click();
    await page.getByText('A geração foi salva.', {exact: false}).waitFor();
    const saved = await state(page);
    assert.equal(saved.bets, before.bets + 2);
    assert.equal(saved.creations, before.creations + 1);
    const replay = await page.request.post(base + '/bets', {headers: {'HX-Request': 'true', 'Content-Type': 'application/x-www-form-urlencoded'},
      // O URLSearchParams preserva os dois campos de mesmo nome.
      data: new URLSearchParams(confirmation).toString()});
    assert.equal(replay.status(), 200);
    assert.deepEqual(await state(page), saved);
    await page.reload();
    assert.equal(await page.locator('#recent-generations .generation-group').count(), 1);
  });
});
test('fechamento/previsão, critérios inválidos e percentual regional BR/EUA', async () => {
  for (const region of ['br', 'us']) await withPage(region, async page => {
    await page.goto(base + '/bets');
    const before = await state(page);
    const preview = page.waitForResponse(r => r.url().includes('/bets/preview') && r.status() === 200);
    await page.locator('#filter-even-min').fill('1');
    await preview;
    assert.match(await page.locator('[data-filter-preview-percent]').inputValue(), region === 'br' ? /^50,0/ : /^50\.0/);
    await page.locator('#closure-numbers').fill('01 02 03 04 05 06 07');
    await page.waitForFunction(() => document.querySelector('#filter-even-min').readOnly);
    await page.locator('#generate-bets').click();
    await page.locator('#generation-result [name=action][value=save_closure]').waitFor({state: 'attached'});
    assert.equal(await page.locator('#generation-result .bet-line').count(), 7);
    assert.deepEqual(await state(page), before);
    await page.locator('#closure-numbers').fill('');
    await page.waitForFunction(() => !document.querySelector('#filter-even-min').readOnly);
    await page.locator('#filter-even-min').fill('5');
    await page.locator('#filter-even-max').fill('1');
    const refused = page.waitForResponse(r => new URL(r.url()).pathname === '/bets' && r.request().method() === 'POST');
    await page.locator('#generate-bets').click();
    assert.equal((await refused).status(), 400);
    assert.equal(await page.locator('#filter-even-min').inputValue(), '5');
    assert.equal(await page.locator('#filter-even-max').inputValue(), '1');
    await page.waitForFunction(() => /mínimo|Mínimo|inválid|maior/.test(document.querySelector('#generation-result').innerText));
    assert.deepEqual(await state(page), before);
  });
});
