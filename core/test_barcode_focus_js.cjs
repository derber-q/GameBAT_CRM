// Проверяет реальные скрипты форм при длинном списке товаров и смене фокуса.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function environment(kind, initialItems = []) {
  const focusLog = [];
  const autocomplete = [];
  let activeElement;
  const camel = value => value.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
  class Element {
    get value() { return this.currentValue || ''; }
    set value(value) { this.currentValue = String(value); }
    constructor(tag = 'div') {
      this.tagName = tag.toUpperCase(); this.children = []; this.dataset = {};
      this.attributes = {}; this.handlers = {}; this.value = ''; this.className = '';
      this.classList = {
        contains: name => this.className.split(' ').includes(name),
        add: (...names) => { this.className = [...new Set([...this.className.split(' '), ...names])].join(' '); },
        remove: (...names) => { this.className = this.className.split(' ').filter(name => !names.includes(name)).join(' '); },
        toggle: (name, enabled) => enabled ? this.classList.add(name) : this.classList.remove(name),
      };
    }
    append(...nodes) { nodes.forEach(node => { node.parentElement = this; this.children.push(node); }); }
    appendChild(node) { this.append(node); }
    replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
    remove() { this.parentElement.children = this.parentElement.children.filter(node => node !== this); }
    matches(selector) {
      selector = selector.trim();
      if (selector.startsWith('.')) return this.classList.contains(selector.slice(1));
      if (selector.includes(':not')) return this.tagName === 'INPUT' && this.type !== 'hidden';
      const match = selector.match(/^(\w+)?(?:\[([^=\]]+)(?:="([^"]*)")?\])?$/);
      if (!match || (match[1] && this.tagName !== match[1].toUpperCase())) return false;
      if (!match[2]) return true;
      const actual = match[2].startsWith('data-') ? this.dataset[camel(match[2].slice(5))] : this[match[2]];
      return match[3] === undefined ? actual !== undefined : String(actual) === match[3];
    }
    querySelectorAll(selector) {
      const found = [];
      for (const child of this.children) {
        if (selector.split(',').some(part => child.matches(part))) found.push(child);
        found.push(...child.querySelectorAll(selector));
      }
      return found;
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    setAttribute(key, value) { this.attributes[key] = value; }
    getAttribute(key) { return this.attributes[key] ?? null; }
    hasAttribute(key) { return key in this.attributes; }
    addEventListener(name, handler) { (this.handlers[name] ||= []).push(handler); }
    dispatchEvent(event) { (this.handlers[event.type] || []).forEach(handler => handler(event)); }
    click() { this.dispatchEvent({ type: 'click' }); }
    focus(options) { activeElement = this; focusLog.push({ element: this, options }); }
    scrollIntoView(options) { this.lastScroll = options; }
    setCustomValidity(message) { this.validationMessage = message; }
  }
  const document = new Element();
  document.createElement = tag => new Element(tag);
  document.getElementById = id => document.querySelector(`[id="${id}"]`);
  const form = new Element('form');
  form.id = kind === 'supply' ? 'supply-form' : 'sale-form';
  form.className = kind === 'sale' ? 'stock-lines-form' : '';
  form.dataset = { autocompleteUrl: '/autocomplete/', searchContext: kind,
    warehouseSelectId: 'id_warehouse', fixedPriceType: 'retail', fixedSaleType: 'retail',
    showSaleInventory: 'true', weightUrl: '/weight/', editing: 'false', initialItemsId: 'initial-sale-items' };
  document.append(form);
  function field(tag, values) { const element = new Element(tag); Object.assign(element, values); form.append(element); return element; }
  const rows = field('tbody', { id: 'supply-lines', className: 'stock-lines' });
  field('input', { id: 'id_warehouse', value: '1' });
  field('input', { name: 'csrfmiddlewaretoken', value: 'test-token' });
  const barcode = field('input', { dataset: { saleBarcodeInput: '' } });
  const barcodeButton = field('button', { dataset: { saleBarcodeAdd: '' } });
  const feedback = field('span', { dataset: { saleBarcodeFeedback: '', supplyBarcodeFeedback: '' } });
  const total = field('strong', { dataset: { saleIntermediateTotal: '' } });
  const commission = field('strong', { dataset: { saleCommissionTotal: '' } });
  const netTotal = field('strong', { dataset: { saleNetTotal: '' } });
  field('script', { id: 'initial-sale-items', textContent: JSON.stringify(initialItems) });
  field('button', { className: kind === 'sale' ? 'add-stock-line' : 'add-supply-line' });
  field('button', { className: 'add-custom-line' });
  field('button', { id: 'add-expense' });
  field('tbody', { id: 'expense-lines' });
  for (const id of ['supplier-data', 'initial-supply-lines', 'initial-expense-lines']) {
    field('script', { id, textContent: '[]' });
  }
  let scanner;
  const requests = [];
  let results = [];
  const context = {
    document, URLSearchParams, Intl, Event: class { constructor(type) { this.type = type; } },
    window: { GameBAT: {
      attachAutocomplete: config => autocomplete.push(config),
      registerGlobalBarcodeHandler: handler => { scanner = handler; },
    }, alert: message => { throw new Error(message); } },
    fetch: async (url, options) => {
      requests.push({ url, options });
      return { ok: true, json: async () => url === '/weight/'
        ? { ok: true, weight_grams: 140 } : { results } };
    },
  };
  const filename = kind === 'sale' ? 'stock-lines.js' : 'supply.js';
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/js', filename), 'utf8'), context);
  focusLog.length = 0;
  function product(index, weight = 140) {
    return { id: index, type: index % 2 ? 'cd' : 'tech', label: `Товар ${index}`,
      barcodes: [`00000000${index}`], available: 100, warehouse_stock: 100,
      weight_grams: weight, prices: { retail: '100.00' } };
  }
  function assertQuantityFocus(row) {
    const quantity = row.querySelector('input[name="quantity"]');
    assert.equal(activeElement, quantity, 'После сканирования фокус должен остаться в количестве товара');
    assert.equal(focusLog.at(-1).options.preventScroll, true);
    assert.equal(quantity.lastScroll.block, 'nearest');
    assert.equal(quantity.lastScroll.inline, 'nearest');
    assert(!focusLog.some(entry => entry.element === barcode), 'Нельзя возвращаться к штрихкоду над списком');
  }
  return { rows, autocomplete, feedback, barcode, barcodeButton, requests, focusLog, product, assertQuantityFocus,
    form, total, commission, netTotal,
    scan: async result => { results = Array.isArray(result) ? result : [result]; await scanner(results[0].barcodes[0]); },
    setResults: value => { results = value; },
  };
}

async function main() {
  for (const kind of ['sale', 'supply']) {
    const env = environment(kind);
    for (let index = 1; index <= 40; index++) {
      await env.scan(env.product(index));
      assert.equal(env.rows.children.length, index);
      env.assertQuantityFocus(env.rows.children.at(-1));
    }
    if (kind === 'sale') {
      const first = env.rows.children[0];
      first.querySelector('input[name="quantity"]').value = '7';
      await env.scan(env.product(1));
      assert.equal(env.rows.children.length, 40);
      assert.equal(first.querySelector('input[name="quantity"]').value, '8');
      env.assertQuantityFocus(first);
      env.barcode.value = env.product(2).barcodes[0];
      env.setResults([env.product(2)]);
      env.barcodeButton.click();
      await new Promise(resolve => setImmediate(resolve));
      assert.equal(new URL(env.requests.at(-1).url, 'http://test').searchParams.get('q'), env.product(2).barcodes[0]);
      env.assertQuantityFocus(env.rows.children[1]);
    } else {
      const last = env.rows.children.at(-1);
      last.querySelector('select[name="supplier_id"]').value = '12';
      last.querySelector('input[name="purchase_unit_cost"]').value = '345.67';
      await env.scan(env.product(40));
      assert.equal(env.rows.children.length, 41, 'Партии прихода сохраняются отдельными строками');
      assert.equal(last.querySelector('select[name="supplier_id"]').value, '12');
      assert.equal(last.querySelector('input[name="purchase_unit_cost"]').value, '345.67');
      await env.scan(env.product(41, 0));
      const weightRow = env.rows.children.at(-1);
      assert.equal(weightRow.querySelector('input[name="product_id"]').value, '');
      const prompt = weightRow.querySelector('.supply-weight-prompt');
      prompt.querySelector('input').value = '140';
      prompt.querySelector('button').click();
      await new Promise(resolve => setImmediate(resolve));
      assert.equal(weightRow.querySelector('input[name="product_id"]').value, '41');
      env.assertQuantityFocus(weightRow);
    }
    const count = env.rows.children.length;
    const duplicate = env.product(50);
    await env.scan([duplicate, { ...duplicate, id: 51 }]);
    assert.equal(env.rows.children.length, count);
    assert.match(env.feedback.textContent, /нескольких товаров/);
    const config = env.autocomplete.at(-1);
    config.onSelect(env.product(60), { exactBarcode: true });
    env.assertQuantityFocus(env.rows.children.at(-1));
  }
  console.log('Сканирование: 40 товаров в продаже и приходе, повторный код, кнопка, автопоиск, партии, вес и неоднозначный код — OK.');
}

module.exports = require.main === module ? main() : { environment, testBarcodeFocus: main };
