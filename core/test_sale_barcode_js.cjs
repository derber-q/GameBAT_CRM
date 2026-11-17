// Будущая регрессия реальной последовательности клавиш сканера; без браузера/сети.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let keydown, tick = 0;
const navigations = [], products = [];
class Element { matches() { return false; } }
const window = {location: {href: 'https://crm.example.invalid/crm/sales/incomplete/', assign: value => navigations.push(value)}};
const document = {
  body: {dataset: {saleBarcodeUrl: '/crm/sales/by-barcode/'}},
  querySelector: () => null, querySelectorAll: () => [],
  getElementById: () => null,
  addEventListener: (event, fn) => { if (event === 'keydown') keydown = fn; },
};
vm.runInNewContext(fs.readFileSync('static/js/app.js', 'utf8'), {
  window, document, Element, HTMLInputElement: class {}, HTMLTextAreaElement: class {}, HTMLSelectElement: class {},
  performance: {now: () => tick}, URL, setInterval() {},
});
window.GameBAT.registerGlobalBarcodeHandler(value => products.push(value));
function scan(text, gap = 10) {
  for (const key of [...text, 'Enter']) {
    tick += gap;
    keydown({key, target: new Element(), preventDefault() {}, stopImmediatePropagation() {}});
  }
}
function scanKeys(keys) {
  for (const key of [...keys, {key: 'Enter'}]) {
    tick += 10;
    keydown({...key, target: new Element(), preventDefault() {}, stopImmediatePropagation() {}});
  }
}
scan('SALE-000594');
assert.equal(navigations[0], 'https://crm.example.invalid/crm/sales/by-barcode/?code=SALE-000594');
assert.equal(products.length, 0);
scan('0012345678901');
assert.equal(products[0], '0012345678901');
scan('https://crm.example.invalid/crm/sales/594/');
assert.equal(navigations.at(-1), 'https://crm.example.invalid/crm/sales/by-barcode/?sale_id=594');
// Старый стикер с адресом локальной CRM и ввод сканера с точками вместо слешей.
scan('https:..crm.example.invalid.crm.sales.595.');
assert.equal(navigations.at(-1), 'https://crm.example.invalid/crm/sales/by-barcode/?sale_id=595');
const english = 'qwertyuiopasdfghjklzxcvbnm', russian = 'йцукенгшщзфывапролдячсмить';
scanKeys([...'https://crm.example.invalid/crm/sales/596/'].map(key => {
  if (key === '/') return {key: '.', code: 'Slash', shiftKey: false};
  if (key === ':') return {key: 'Ж', code: 'Semicolon', shiftKey: true};
  if (key === '.') return {key: 'ю', code: 'Period', shiftKey: false};
  if (/[a-z]/.test(key)) return {key: russian[english.indexOf(key)], code: 'Key' + key.toUpperCase(), shiftKey: false};
  return {key, code: 'Digit' + key, shiftKey: false};
}));
assert.equal(navigations.at(-1), 'https://crm.example.invalid/crm/sales/by-barcode/?sale_id=596');
const count = navigations.length;
scan('SALE-000595', 200); // Обычный медленный ввод не является сканированием.
assert.equal(navigations.length, count);
