const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor(tag = 'div') {
    Object.assign(this, {tagName: tag, children: [], dataset: {}, listeners: {}, value: '',
      textContent: '', disabled: false, hidden: false, open: false, attributes: {}});
  }
  addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }
  setAttribute(name, value) { this.attributes[name] = value; }
  appendChild(child) {
    this.children.push(child);
    if (this.tagName === 'select' && this.children.length === 1) this.value = child.value;
  }
  replaceChildren() { this.children = []; this.value = ''; }
  querySelectorAll(selector) {
    const tags = selector.split(',').map(tag => tag.trim());
    return this.children.flatMap(child => [
      ...(tags.includes(child.tagName) ? [child] : []),
      ...child.querySelectorAll(selector),
    ]);
  }
  reportValidity() { return true; }
  showModal() { this.open = true; this.opens = (this.opens || 0) + 1; }
  close() { this.open = false; }
  async fire(type) {
    for (const callback of this.listeners[type] || []) await callback({preventDefault() {}});
    await new Promise(resolve => setImmediate(resolve));
  }
}

function environment(overrides = {}, requested = 0, response) {
  const line = {name: 'Игра', quantity: 10, url: '/line/1/', price_supplier_id: 1,
    is_last_supplier: true, priority_ambiguous: false,
    targets: [{id: 3, name: 'Другой', priority: 3}], prices: [{id: 1, name: 'Первый', price: '100'}],
    allocations: [{allocation_id: 11, order_id: 1, recipient: 'Первый', current: 5, elsewhere: 0},
      {allocation_id: 12, order_id: 2, recipient: 'Второй', current: 5, elsewhere: 0}], ...overrides};
  const ids = Object.fromEntries(['editor-data', 'change-dialog', 'change-form', 'action', 'target-supplier',
    'price-supplier', 'change-error', 'customer-rows', 'change-save', 'page-error', 'transfer-fields',
    'allocation-fields', 'automatic-adjustment', 'allocation-total', 'change-product', 'change-amount',
    'change-mode', 'priority-ambiguity', 'change-cancel'].map(id => ['trip-' + id, new Element()]));
  const get = id => ids['trip-' + id];
  get('editor-data').textContent = JSON.stringify({'1': line});
  for (const id of ['action', 'target-supplier', 'price-supplier']) get(id).tagName = 'select';
  get('change-form').dataset.revision = '7';
  const source = new Element('form');
  source.dataset.lineId = '1';
  const quantity = new Element('input');
  quantity.value = String(requested);
  source.elements = {quantity};
  source.children.push(quantity, new Element('button'));
  const calls = [];
  let reloads = 0;
  class FormData {
    constructor() {
      this.values = new Map([['csrfmiddlewaretoken', 'test-csrf']]);
      for (const [name, id] of [['action', 'action'], ['target_supplier', 'target-supplier'], ['price_supplier', 'price-supplier']]) {
        if (!get(id).disabled) this.set(name, get(id).value);
      }
    }
    set(name, value) { this.values.set(name, value); }
    get(name) { return this.values.get(name); }
  }
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/js/order-trips.js'), 'utf8'), {
    document: {getElementById: id => ids[id], createElement: tag => new Element(tag),
      querySelectorAll: selector => selector === '.trip-line-form' ? [source] : []},
    FormData, window: {location: {reload() { reloads++; }}},
    fetch: async (url, options) => {
      calls.push({url, ...options});
      return response ? response() : {ok: true, headers: {get: () => 'application/json'}, json: async () => ({success: true})};
    },
  });
  return {get, source, calls, line, quantity, reloads: () => reloads,
    inputs: () => get('customer-rows').querySelectorAll('input')};
}

async function main() {
  for (const [allocations, quantity] of [
    [[5, 3, 2].map((current, index) => ({allocation_id: index + 1, current, elsewhere: 0})), 0],
    [[{allocation_id: 1, current: 12, elsewhere: 2}, {allocation_id: 2, current: 4, elsewhere: 4}], 6],
  ]) {
    const env = environment({allocations}, quantity);
    await env.source.fire('submit');
    assert.equal(env.get('change-dialog').opens, undefined);
    assert.equal(env.calls.length, 1);
    assert.equal(env.calls[0].body.get('action'), 'adjust');
    assert.equal(env.calls[0].body.get('distribution'), 'null');
    assert.equal(env.calls[0].body.get('quantity'), String(quantity));
    assert.equal(env.calls[0].body.get('revision'), '7');
    assert.equal(env.calls[0].body.get('csrfmiddlewaretoken'), 'test-csrf');
    assert.equal(env.reloads(), 1);
    await env.source.fire('submit');
    assert.equal(env.calls.length, 1);
  }

  const manual = environment({}, 7);
  await manual.source.fire('submit');
  assert.equal(manual.get('change-dialog').open, true);
  assert.equal(manual.get('change-mode').hidden, true);
  assert.equal(manual.get('transfer-fields').hidden, true);
  assert.equal(manual.get('allocation-fields').hidden, false);
  await manual.get('change-form').fire('submit');
  assert.equal(manual.calls.length, 0);
  assert.match(manual.get('change-error').textContent, /Распределите количество/);
  manual.inputs()[0].value = '5';
  manual.inputs()[1].value = '2';
  await manual.get('change-form').fire('submit');
  assert.deepEqual(JSON.parse(manual.calls[0].body.get('distribution')),
    [{allocation_id: 11, final_quantity: '5'}, {allocation_id: 12, final_quantity: '2'}]);

  for (const requested of [0, 6]) {
    const choice = environment({is_last_supplier: false, allocations: [
      {allocation_id: 11, order_id: 1, current: 10, elsewhere: 0}]}, requested);
    await choice.source.fire('submit');
    assert.equal(choice.get('change-mode').hidden, false);
    assert.equal(choice.get('action').value, 'transfer');
    assert.equal(choice.calls.length, 0);
    choice.get('action').value = 'adjust';
    await choice.get('action').fire('change');
    assert.equal(choice.get('allocation-fields').hidden, true);
    assert.equal(choice.get('automatic-adjustment').hidden, false);
    await choice.get('change-form').fire('submit');
    assert.equal(choice.calls[0].body.get('distribution'), 'null');
    assert.equal(choice.calls[0].body.get('target_supplier'), undefined);
  }

  const transfer = environment({is_last_supplier: false, priority_ambiguous: true}, 6);
  await transfer.source.fire('submit');
  assert.equal(transfer.get('priority-ambiguity').hidden, false);
  await transfer.get('change-form').fire('submit');
  assert.equal(transfer.calls[0].body.get('action'), 'transfer');
  assert.equal(transfer.calls[0].body.get('target_supplier'), '3');
  assert.equal(transfer.calls[0].body.get('price_supplier'), '1');
  assert.equal(transfer.calls[0].body.get('distribution'), 'null');

  const increase = environment({quantity: 0, allocations: [{allocation_id: 11, current: 0, elsewhere: 0}]}, 2);
  await increase.source.fire('submit');
  assert.equal(increase.get('allocation-fields').hidden, false);
  assert.equal(increase.calls.length, 0);
  await increase.get('change-cancel').fire('click');
  await increase.get('change-form').fire('submit');
  assert.equal(increase.calls.length, 0);
  assert.equal(increase.get('change-dialog').open, false);

  let reject;
  const failure = environment({}, 0, () => new Promise((resolve, rejectRequest) => { reject = rejectRequest; }));
  await failure.source.fire('submit');
  assert.equal(failure.quantity.disabled, true);
  await failure.source.fire('submit');
  assert.equal(failure.calls.length, 1);
  reject(new Error('База занята'));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(failure.quantity.disabled, false);
  assert.equal(failure.get('change-save').disabled, false);
  assert.equal(failure.get('page-error').textContent, 'База занята');
  assert.equal(failure.reloads(), 0);
  assert.equal(failure.line.quantity, 10);
  console.log('Рейсы: приоритеты, ноль, один заказ, ручная сумма, перенос, восстановление и повтор запроса — OK.');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
