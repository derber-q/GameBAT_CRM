const assert = require('node:assert/strict');
const { environment } = require('../core/test_barcode_focus_js.cjs');

function controls(row) {
  return { sign: row.querySelector('[data-discount-sign]'),
    amount: row.querySelector('[data-discount-amount]'),
    signed: row.querySelector('input[name="unit_discount"]') || row.querySelector('input[name="custom_unit_discount"]') };
}
function adjust(row, sign, amount) {
  const fields = controls(row);
  fields.sign.value = sign;
  fields.amount.value = amount;
  fields.amount.dispatchEvent({ type: 'input' });
  return fields;
}
function standard(unit_price = '500.00', unit_discount = '0.00') {
  return { product_type: 'cd', product_id: 1, label: 'Игра', quantity: 2, unit_price, unit_discount, warehouse_stock: 100 };
}
const money = output => output.textContent.replace(/[\s\u00a0\u202f]/g, '');

const env = environment('sale', [standard()]);
const row = env.rows.children[0];
assert.equal(controls(row).sign.value, '-');
assert.equal(money(env.total), '1000,00₽');
assert.equal(adjust(row, '-', '50').signed.value, '50.00');
assert.equal(money(env.total), '900,00₽');
controls(row).sign.value = '+';
controls(row).sign.dispatchEvent({ type: 'change' });
assert.equal(controls(row).signed.value, '-50.00');
assert.equal(money(env.total), '1100,00₽');
assert.equal(adjust(row, '+', '0.01').signed.value, '-0.01');
assert.equal(money(env.total), '1000,02₽');
adjust(row, '-', '500');
assert.equal(money(env.total), '0,00₽');

const restored = environment('sale', [standard('500.00', '-25.10'),
  { custom: true, name: 'Услуга', quantity: 3, unit_price: '80.00', unit_discount: '-10.01', unit_cost: '0' }]);
assert.equal(controls(restored.rows.children[0]).sign.value, '+');
assert.equal(controls(restored.rows.children[0]).amount.value, '25.10');
assert.equal(controls(restored.rows.children[1]).signed.value, '-10.01');
assert.equal(money(restored.total), '1320,23₽');
adjust(restored.rows.children[1], '-', '10.01');
assert.equal(money(restored.total), '1260,17₽');

const large = environment('sale', [standard('999999999999999999.00', '-0.01')]);
assert.equal(money(large.total), '1999999999999999998,02₽');

// Комиссия округляется в копейках по той же формуле ROUND_HALF_UP, что на сервере.
env.form.dataset.fixedSaleType = 'avito';
adjust(row, '+', '1.00');
assert.equal(money(env.commission), '5,01₽');
assert.equal(money(env.netTotal), '996,99₽');
const zero = adjust(row, '-', '500');
assert.equal(money(env.commission), '1,00₽');
zero.amount.value = '499.00'; zero.amount.dispatchEvent({ type: 'input' });
assert.equal(money(env.commission), '1,00₽');

console.log('Скидки и доплаты: знаки, создание, восстановление, произвольные строки, копейки, большие суммы и комиссия — OK.');
