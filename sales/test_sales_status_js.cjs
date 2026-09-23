const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const callbacks = {};
const elements = {};
for (const id of ['sale-status-dialog', 'sale-status-confirm-form', 'sale-status-question', 'sale-status-cash-field', 'sale-status-cash', 'sales-status-message', 'sale-status-cancel']) {
  elements[id] = {textContent: '', addEventListener: (event, fn) => callbacks[id + ':' + event] = fn};
}
let opened = false, calls = 0, resolve, requestData, removed = false;
elements['sale-status-dialog'].showModal = () => opened = true;
elements['sale-status-dialog'].close = () => opened = false;
const count = {textContent: '1'}, empty = {hidden: true};
const group = {querySelector: (selector) => selector === '[data-sale-count]' ? count : selector === '[data-sale-empty]' ? empty : (removed ? null : row)};
const select = {
  value: 'assembled', dataset: {current: 'created', statusField: 'order'},
  options: [{textContent: 'Создан'}, {textContent: 'Собран'}],
  get selectedIndex() {return this.value === this.dataset.current ? 0 : 1;},
  closest: (selector) => selector === '[data-status-field]' ? select : row,
};
const row = {
  dataset: {saleId: 'SALE-000001', version: 'v1', statusUrl: '/sales/1/status/', paymentMethod: 'cash_postpay', total: '100'},
  querySelectorAll: () => [select], closest: () => group, remove: () => removed = true,
};
vm.runInNewContext(fs.readFileSync('static/js/sales-status.js', 'utf8'), {
  document: {getElementById: (id) => elements[id], addEventListener: (event, fn) => callbacks[event] = fn},
  FormData: class extends Map {constructor() {super();}},
  fetch: (url, options) => {
    calls++; requestData = options.body;
    assert.equal(url, '/sales/1/status/'); assert.equal(options.method, 'POST');
    return new Promise((done) => resolve = done);
  },
});
const change = () => callbacks.change({target: select});
const submit = () => callbacks['sale-status-confirm-form:submit']({preventDefault() {}});
const reply = (result) => resolve({headers: {get: () => 'application/json'}, json: async () => result});
(async () => {
  change(); assert(opened); assert.equal(calls, 0); assert.equal(select.value, 'created');
  assert(elements['sale-status-question'].textContent.includes('«Создан» на «Собран»'));
  callbacks['sale-status-cancel:click'](); await submit(); assert.equal(calls, 0);
  select.value = 'assembled'; change(); callbacks['sale-status-dialog:cancel'](); await submit(); assert.equal(calls, 0);
  select.value = 'assembled'; change(); const saving = submit(); await submit();
  assert.equal(calls, 1); assert.equal(select.disabled, true);
  assert.equal(requestData.get('confirmed'), '1'); assert.equal(requestData.get('version'), 'v1');
  reply({success: true, row_html: '<tr>actual assembled</tr>', message: 'OK'}); await saving;
  assert.equal(row.outerHTML, '<tr>actual assembled</tr>'); assert.equal(select.disabled, false);
  select.dataset.current = 'unpaid'; select.dataset.statusField = 'payment';
  select.options = [{textContent: 'Не оплачен'}, {textContent: 'Оплачен'}]; select.value = 'paid';
  change(); assert.equal(elements['sale-status-cash-field'].hidden, false); assert.equal(calls, 1);
  const payment = submit(); reply({success: false, row_html: '<tr>actual unpaid</tr>', message: 'Касса недоступна'}); await payment;
  assert.equal(row.outerHTML, '<tr>actual unpaid</tr>'); assert(!removed);
  assert(elements['sales-status-message'].textContent.includes('Касса недоступна'));
  select.value = 'paid'; change(); const completed = submit();
  reply({success: true, is_completed: true, message: 'OK'}); await completed;
  assert(removed); assert.equal(Number(count.textContent), 0); assert.equal(empty.hidden, false);
  console.log('Sale status JS: confirmation/cancel/Escape, no optimistic status, double-submit, payment errors, completion and empty group OK');
})().catch((error) => {console.error(error); process.exitCode = 1;});
