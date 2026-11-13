// Количество единиц в форме: изменяем состав, не создавая продаж и не обращаясь к API.
const assert = require('node:assert/strict');
const { environment } = require('../core/test_barcode_focus_js.cjs');
const value = env => env.units.textContent.replace(/\s/g, '');

async function main() {
  const env = environment('sale');
  assert.equal(value(env), '0шт.');
  await env.scan(env.product(1));
  const first = env.rows.children[0];
  const quantity = first.querySelector('input[name="quantity"]');
  quantity.value = '7'; quantity.dispatchEvent({type:'input'});
  assert.equal(value(env), '7шт.');
  await env.scan(env.product(2));
  assert.equal(value(env), '8шт.');
  first.querySelector('.remove-row').click();
  assert.equal(value(env), '1шт.');
  const secondQuantity = env.rows.children[0].querySelector('input[name="quantity"]');
  secondQuantity.value = '1.5'; secondQuantity.dispatchEvent({type:'input'});
  assert.equal(value(env), '0шт.');
  env.form.querySelector('.add-custom-line').click();
  const custom = env.rows.children[1];
  custom.querySelector('input[name="custom_name"]').value = 'Произвольный товар';
  const customQuantity = custom.querySelector('input[name="custom_quantity"]');
  customQuantity.value = '3'; customQuantity.dispatchEvent({type:'input'});
  assert.equal(value(env), '3шт.');
}
main().catch(error => { console.error(error); process.exitCode=1; });
