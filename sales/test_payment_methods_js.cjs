const assert = require('node:assert/strict');
const { environment } = require('../core/test_barcode_focus_js.cjs');

const env = environment('sale', [{ product_type: 'cd', product_id: 1, label: 'Игра', quantity: 1,
  unit_price: '10000.00', warehouse_stock: 100 }], true);
const change = (field, value) => { field.value = value; field.dispatchEvent({type: 'change'}); };
assert.equal(env.receivedContainer.hidden, false);
assert.match(env.paymentHint.textContent, /сразу завершена/);
for (const channel of ['avito', 'yandex_market']) {
  change(env.saleType, channel);
  assert.equal(env.payment.value, 'bank_transfer_postpay');
  assert.equal(env.receivedContainer.hidden, true);
  assert.equal(env.received.disabled, true);
  assert.match(env.paymentHint.textContent, /после доставки и оплаты/);
  change(env.payment, 'bank_account');
  assert.equal(env.receivedContainer.hidden, false);
  assert.equal(env.received.disabled, false);
  assert.match(env.paymentHint.textContent, /сразу завершена/);
}
change(env.saleType, 'retail');
assert.equal(env.payment.value, 'bank_account');
for (const method of ['cash_postpay', 'bank_transfer_postpay']) {
  change(env.payment, method);
  assert.equal(env.received.disabled, true);
}
change(env.payment, 'bank_account');
env.received.value = '9999.99';
assert.throws(() => env.form.dispatchEvent({type: 'submit', preventDefault() {}}), /не может быть меньше/);
env.received.value = '10500.01';
env.form.dispatchEvent({type: 'submit', preventDefault() {throw new Error('Лишний запрет');}});
console.log('Способы оплаты: маркетплейсы, ручной выбор, постоплата и суммы банковского перевода — OK.');
