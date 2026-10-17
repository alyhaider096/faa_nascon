// Contract smoke tests without a running phone or backend. Never touches real orders.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../src/data/api.ts'), 'utf8');
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
let reply;
let captured;
const sandbox = { exports: {}, AbortController, setTimeout, clearTimeout, fetch: async (url, options) => { captured = { url, options }; return reply; } };
vm.runInNewContext(code, sandbox);
const api = sandbox.exports;
async function main() {
  const product = api.productFromServer({ product_id: 'p1', name: 'Jersey', category: 'kit', variants: [{ variant_id: 'v1', attributes: { size: 'M' }, price_minor: 450000, stock: 1 }] });
  assert.equal(product.variants[0].id, 'v1');
  assert.equal(product.variants[0].priceMinor, 450000);
  assert.equal(product.variants[0].label, 'M');
  const match = api.matchFromServer({ match_id: 'm1', sport_id: 'custom-sport', league_id: 'l1', status: 'in_progress', version: 1, home: { team_id: 'h', score: 2 }, away: { team_id: 'a', score: 1 }, events: [] });
  assert.equal(match.status, 'Live');
  assert.equal(match.score, '2 : 1');
  assert.equal(match.eventTypes.length, 0); // Never invent sport rules.
  reply = { ok: true, json: async () => ({ accepted: true }) };
  await api.request('http://localhost:8080', '/api/v1/checkout', 'test-token', { items: [] });
  assert.equal(captured.options.headers.Authorization, 'Bearer test-token');
  assert.equal(captured.options.method, 'POST');
  for (const status of [401, 403, 409, 429]) {
    reply = { ok: false, status, json: async () => ({ error: { code: 'TEST', message: 'Server explanation' } }) };
    await assert.rejects(api.request('http://localhost', '/api/v1/test', null), e => e.status === status && e.message === (status === 403 ? 'Not allowed. Your role cannot perform this action.' : 'Server explanation'));
  }
  console.log('PASS: product/score adapters, bearer authorization, POST body, 401/403/409/429 errors');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
