const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function runtime(saved = {}) {
  let listener;
  const tabs = new Map([[1, {id: 1, url: 'http://127.0.0.1:8000/crm/pricing/avito-check/'}]]);
  const calls = [];
  const data = structuredClone(saved);
  const items = [1, 2].map(id => ({id, name: 'Игра ' + id, price: '100.25', recorded_at: 'old', search_url: 'https://www.avito.ru/all?q=game' + id}));
  let failSave = false;
  const chrome = {runtime: {id: 'test-extension', onMessage: {addListener(fn) { listener = fn; }}},
    storage: {session: {
      async get(key) { return structuredClone({[key]: data[key]}); },
      async set(value) { Object.assign(data, structuredClone(value)); },
      async remove(key) { delete data[key]; }
    }}, tabs: {
      async get(id) { if (!tabs.has(id)) throw new Error('Closed'); return tabs.get(id); },
      async create() { const tab = {id: tabs.size + 1}; tabs.set(tab.id, tab); return tab; },
      async update(id, values) { Object.assign(tabs.get(id), values); calls.push(['navigate', values.url]); },
      async sendMessage(id, message) {
        calls.push(['bridge', message]);
        if (message.action === 'queue') return {ok: true, items};
        if (message.action === 'product') return {ok: true, product: items.find(p => p.id === message.productId)};
        if (failSave) return {ok: false, message: 'CRM не сохранила цену'};
        return {ok: true};
      }, onRemoved: {addListener() {}}
    }};
  const context = vm.createContext({chrome, URL, console, structuredClone});
  context.importScripts = name => vm.runInContext(fs.readFileSync(path.join(__dirname, name), 'utf8'), context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, 'background.js'), 'utf8'), context);
  const sender = (tabId = 2, url = 'https://www.avito.ru/all?q=game1') => ({id: chrome.runtime.id, frameId: 0, tab: {id: tabId}, url});
  const send = (action, message = {}, from = sender()) => new Promise(resolve => {
    assert.equal(listener({type: 'resource-avito:' + action, ...message}, from, resolve), true);
  });
  return {send, sender, tabs, calls, items, data, protocol: context.ResourceAvito, setFailSave(value) { failSave = value; }};
}

(async () => {
  const app = runtime();
  assert.equal(app.protocol.price('3 450,25'), '3450.25');
  assert.equal(app.protocol.price('999999999999999999.99'), '999999999999999999.99');
  for (const value of ['', '0', '-1', 'NaN', '1e3', '1.234', '1000000000000000000']) assert.throws(() => app.protocol.price(value));
  assert.equal((await app.send('start', {productId: 1}, app.sender(1, app.tabs.get(1).url))).ok, true);
  assert.equal(app.tabs.get(2).url, app.items[0].search_url);
  assert.equal((await app.send('current')).product.price, '100.25');
  const before = app.calls.length;
  assert.equal((await app.send('save', {productId: 1, price: '-1'})).ok, false);
  assert.equal(app.calls.length, before);
  app.setFailSave(true);
  assert.equal((await app.send('save', {productId: 1, price: '99', version: 'old'})).ok, false);
  assert.equal(app.data['2'].index, 0);
  app.setFailSave(false);
  const results = await Promise.all([1, 2].map(() => app.send('save', {productId: 1, price: '99,50', version: 'old'})));
  assert.equal(results[0].nextUrl, app.items[1].search_url);
  assert.equal(results[1].ok, false);
  assert.equal(app.data['2'].completed, 1);
  const saveCalls = app.calls.filter(([kind, msg]) => kind === 'bridge' && msg.action === 'save');
  assert.equal(saveCalls.at(-1)[1].price, '99.50');
  assert.equal(saveCalls.at(-1)[1].version, 'old');
  assert.equal((await app.send('current')).product.id, 2);
  assert.equal((await app.send('skip', {productId: 2})).done, true);
  assert.equal((await app.send('current')).completed, 1);
  assert.equal((await app.send('current', {}, app.sender(99))).inactive, true);
  assert.equal((await app.send('start', {productId: 1})).ok, false);
  assert.equal((await app.send('current', {}, app.sender(2, 'https://avito.ru.evil.example/'))).ok, false);
  assert.equal((await app.send('current', {}, {...app.sender(), id: 'other-extension'})).ok, false);
  const restored = runtime(app.data);
  assert.equal((await restored.send('current')).done, true);
  const closed = runtime();
  await closed.send('start', {productId: 1}, closed.sender(1, closed.tabs.get(1).url));
  closed.tabs.delete(1);
  assert.equal((await closed.send('current')).ok, false);
  const invalid = runtime();
  invalid.items[0].search_url = 'https://evil.example/';
  assert.equal((await invalid.send('start', {productId: 1}, invalid.sender(1, invalid.tabs.get(1).url))).ok, false);
  assert.equal(invalid.tabs.size, 1);
  console.log('Avito extension: queue, exact money, prefill, failed/duplicate saves, restart and origin guards OK');
})().catch(error => { console.error(error); process.exitCode = 1; });
