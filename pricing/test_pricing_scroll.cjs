const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const code = fs.readFileSync('static/js/pricing-scroll.js', 'utf8');
let submit, edited, calls = 0, prevented = 0, resolveResponse;
const button = {disabled: false};
const status = {style: {}, setAttribute() {}};
const input = {value: '189', matches: () => true, addEventListener: (_, fn) => edited = fn};
const form = {
  action: '/pricing/update/', elements: [input],
  querySelector: () => button, appendChild() {}, addEventListener: (_, fn) => submit = fn,
};
const context = {
  document: {
    querySelectorAll: () => [form], createElement: () => status,
  },
  FormData: class {constructor(value) {assert.equal(value, form);}},
  fetch: (url, options) => {
    calls++;
    assert.equal(url, form.action);
    assert.equal(options.headers['X-Requested-With'], 'XMLHttpRequest');
    assert.equal(options.method, 'POST');
    return new Promise((resolve) => resolveResponse = resolve);
  },
};
vm.runInNewContext(code, context);
const event = {preventDefault() {prevented++;}};
const response = (ok, message) => ({ok, headers: {get: () => 'application/json'}, json: async () => ({ok, message})});
(async () => {
  let pending = submit(event);
  assert.equal(button.disabled, true);
  await submit(event); assert.equal(calls, 1); // no double save
  resolveResponse(response(true)); await pending;
  assert.equal(status.textContent, 'Сохранено'); assert.equal(button.disabled, false);
  input.value = '200'; edited(); assert.equal(status.textContent, 'Не сохранено');
  pending = submit(event); input.value = '201';
  resolveResponse(response(true)); await pending;
  assert(status.textContent.includes('несохранённые')); assert.equal(input.value, '201');
  pending = submit(event); resolveResponse(response(false, 'Цена неверна')); await pending;
  assert.equal(status.textContent, 'Цена неверна'); assert.equal(button.disabled, false);
  pending = submit(event); resolveResponse({headers: {get: () => 'text/html'}}); await pending;
  assert(status.textContent.includes('вход в аккаунт')); assert.equal(button.disabled, false);
  context.fetch = async () => {throw new Error('Network error');};
  await submit(event); assert.equal(status.textContent, 'Network error');
  assert.equal(prevented, 6);
  console.log('Pricing async save: no navigation, JSON success/errors, double-submit, pending edits, auth and network errors OK');
})().catch((error) => {console.error(error); process.exitCode = 1;});
