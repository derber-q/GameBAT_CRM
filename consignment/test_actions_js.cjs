const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const callbacks = {}, elements = {};
const ids = ['action-dialog', 'action-form', 'action-quantity', 'action-warehouse', 'action-payment', 'action-message', 'action-cancel', 'action-title', 'action-product', 'action-available', 'quantity-field', 'return-field', 'payment-field', 'action-summary'];
ids.forEach((id) => elements['consignment-' + id] = {value: '', textContent: '', options: [{textContent: 'Choose'}, {textContent: 'Warehouse B'}], selectedIndex: 1,
  addEventListener: (event, fn) => callbacks[id + ':' + event] = fn});
let opened = false, removed = false, calls = 0, resolve, posted;
elements['consignment-action-dialog'].showModal = () => opened = true;
elements['consignment-action-dialog'].close = () => opened = false;
elements['consignment-action-form'].reportValidity = () => true;
const groupCount = {}, platformCount = {}, empty = {};
const group = {querySelectorAll: () => removed ? [] : [row], querySelector: () => groupCount};
const platform = {querySelectorAll: () => removed ? [] : [row], querySelector: (selector) => selector === '[data-platform-count]' ? platformCount : empty};
const button = {dataset: {consignmentAction: 'return'}, closest: (selector) => selector === '[data-consignment-action]' ? button : row};
const row = {dataset: {quantity: '1', name: 'Disc', platform: 'Partner', token: 'signed', actionUrl: '/row/'},
  querySelectorAll: () => [button], closest: (selector) => selector === '.consignment-product-group' ? group : platform, remove: () => removed = true};
vm.runInNewContext(fs.readFileSync('static/js/consignment-actions.js', 'utf8'), {
  document: {getElementById: (id) => elements[id], addEventListener: (event, fn) => callbacks[event] = fn},
  FormData: class extends Map {constructor() {super(); this.set('quantity', elements['consignment-action-quantity'].value);}},
  fetch: (_, options) => {calls++; posted = options.body; return new Promise((done) => resolve = done);},
});
const click = () => callbacks.click({target: button});
const submit = () => callbacks['action-form:submit']({preventDefault() {}});
const reply = (data) => resolve({headers: {get: () => 'application/json'}, json: async () => data});
(async () => {
  click(); assert(opened); assert.equal(calls, 0);
  assert.equal(elements['consignment-quantity-field'].hidden, true);
  assert.equal(elements['consignment-action-quantity'].value, '1');
  assert.equal(elements['consignment-action-warehouse'].value, ''); // no automatic warehouse
  assert.equal(elements['consignment-action-payment'].disabled, true);
  callbacks['action-cancel:click'](); await submit(); assert.equal(calls, 0);
  row.dataset.quantity = '5'; click();
  assert.equal(elements['consignment-quantity-field'].hidden, false);
  assert.equal(elements['consignment-action-quantity'].value, '');
  assert.equal(elements['consignment-action-quantity'].max, '5');
  callbacks['action-dialog:cancel'](); await submit(); assert.equal(calls, 0);
  click(); elements['consignment-action-quantity'].value = '2';
  const returning = submit(); await submit(); assert.equal(calls, 1); assert.equal(button.disabled, true);
  assert.equal(posted.get('quantity'), '2'); assert.equal(posted.get('confirmed'), '1'); assert.equal(posted.get('token'), 'signed');
  reply({success: true, quantity: 3, row_html: '<tr>actual quantity 3</tr>', message: 'Returned'}); await returning;
  assert.equal(row.outerHTML, '<tr>actual quantity 3</tr>'); assert(!removed); assert.equal(button.disabled, false);
  button.dataset.consignmentAction = 'sold'; row.dataset.quantity = '1'; click();
  assert.equal(elements['consignment-action-warehouse'].disabled, true);
  assert.equal(elements['consignment-action-payment'].disabled, false);
  const rejected = submit(); reply({success: false, row_html: '<tr>actual stock</tr>', message: 'Not enough'}); await rejected;
  assert(elements['consignment-action-message'].textContent.includes('Not enough'));
  click(); const sold = submit(); reply({success: true, quantity: 0, row_html: '', message: 'Sold'}); await sold;
  assert(removed); assert.equal(group.hidden, true); assert.equal(empty.hidden, false);
  console.log('Consignment JS: single/multiple quantity, manual warehouse, confirm/cancel/Escape, duplicate submit, errors and empty state OK');
})().catch((error) => {console.error(error); process.exitCode = 1;});
