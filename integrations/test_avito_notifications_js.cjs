const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

(async () => {
  const source = fs.readFileSync(path.join(__dirname, '../static/js/avito-notifications.js'), 'utf8');
  const badge = {textContent: '2'};
  const attributes = {};
  const counter = {dataset: {countUrl: '/actions/count/'}, title: '', pending: false,
    querySelector: () => badge, setAttribute: (name, value) => {attributes[name] = value;},
    classList: {toggle: (name, value) => {assert.equal(name, 'has-pending'); counter.pending = value;}}};
  const events = {};
  let tick, calls = 0, payload = {count: 2, publish: 1, unpublish: 1}, failed = false;
  const document = {hidden: false, querySelectorAll: () => [counter],
    addEventListener: (name, callback) => {events[name] = callback;}};
  const context = {document, window: {addEventListener: (name, callback) => {events[name] = callback;}},
    AbortController, setTimeout, clearTimeout, setInterval: callback => {tick = callback;},
    fetch: async (url, options) => {
      calls++;
      assert.equal(url, '/actions/count/?events=1');
      assert.equal(options.credentials, 'same-origin');
      assert.equal(options.cache, 'no-store');
      return {ok: !failed, headers: {get: () => 'application/json'}, json: async () => payload};
    }};
  const flush = () => new Promise(resolve => setImmediate(resolve));
  vm.runInNewContext(source, context);
  await flush();
  assert.equal(badge.textContent, 2);
  assert.equal(counter.pending, true);
  assert.match(counter.title, /опубликовать — 1, снять — 1/);
  payload = {count: 0, publish: 0, unpublish: 0};
  tick(); await flush();
  assert.equal(badge.textContent, 0);
  assert.equal(counter.pending, false);
  assert.match(attributes['aria-label'], /— 0$/);
  payload = {count: 3, publish: 2, unpublish: 1};
  events.online(); await flush();
  failed = true;
  tick(); await flush();
  assert.equal(badge.textContent, 3);
  assert.equal(counter.pending, true);
  assert.match(counter.title, /последние данные/);
  failed = false;
  payload = {count: 99, publish: 0, unpublish: 0};
  tick(); await flush();
  assert.equal(badge.textContent, 3);
  document.hidden = true;
  const before = calls;
  tick(); await flush();
  assert.equal(calls, before);
  document.hidden = false;
  payload = {count: 0, publish: 0, unpublish: 0};
  events.visibilitychange(); await flush();
  assert.equal(badge.textContent, 0);
  assert.equal(counter.pending, false);
  vm.runInNewContext(source, {document: {querySelectorAll: () => []}});
  console.log('Avito: counter, publish/unpublish totals, zero, recovery and retained offline count — OK');
})().catch(error => {console.error(error); process.exitCode = 1;});
