const assert = require('node:assert/strict');
const {environment} = require('../core/test_barcode_focus_js.cjs');

const items = [{product_type: 'cd', product_id: 1, label: 'Игра', quantity: 2,
  prices: {retail: '200.00', wholesale: '150.00', yandex_market: '220.00'}, warehouse_stock: 10}];
const change = (input, value) => {input.value = value; input.dispatchEvent({type: 'change'});};
const env = environment('sale', items, true, {});
const wholesale = env.priceType.querySelector('option[value="wholesale"]');
assert.equal(wholesale.disabled, true);
assert.equal(wholesale.hidden, true);
change(env.saleType, 'wholesale');
assert.equal(env.priceType.value, 'wholesale');
assert.equal(wholesale.disabled, false);
assert.match(env.total.textContent, /300,00/);
for (const [channel, price, total] of [['retail', 'retail', '400,00'], ['avito', 'retail', '400,00']]) {
  change(env.saleType, 'wholesale');
  change(env.saleType, channel);
  assert.equal(env.priceType.value, price);
  assert.equal(wholesale.disabled, true);
  assert.equal(wholesale.hidden, true);
  assert(env.total.textContent.includes(total));
}
const loaded = environment('sale', items, true, {saleType: 'wholesale', priceType: 'wholesale'});
assert.equal(loaded.priceType.value, 'wholesale');
assert.match(loaded.total.textContent, /300,00/);
console.log('Оптовая цена: автоматический выбор, пересчёт состава и запрет для других типов продаж — OK');
