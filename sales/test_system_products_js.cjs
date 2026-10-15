const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { environment } = require('../core/test_barcode_focus_js.cjs');

const special = kind => ({type: 'system', id: kind, system_kind: kind,
  label: kind === 'EXPENSE' ? 'Расход' : 'Цифровой товар', available: null,
  barcodes: [kind === 'EXPENSE' ? '000000001234' : '000000005678']});

async function main() {
  const env = environment('sale');
  await env.scan(special('DIGITAL_PRODUCT'));
  assert.equal(env.rows.children.length, 1);
  const first = env.rows.children[0];
  first.querySelector('input[name="custom_unit_cost"]').value = '2000';
  first.querySelector('input[name="custom_unit_price"]').value = '2500';
  await env.scan(special('DIGITAL_PRODUCT'));
  assert.equal(env.rows.children.length, 2, 'Повторный цифровой код создаёт независимую строку');
  assert.equal(first.querySelector('input[name="custom_unit_cost"]').value, '2000');
  assert.equal(first.querySelector('input[name="custom_unit_price"]').value, '2500');
  await env.scan(special('EXPENSE'));
  await env.scan(env.product(1));
  assert.equal(env.rows.children.length, 2);
  assert.match(env.feedback.textContent, /отдельной продажей/);
  env.form.querySelector('.add-custom-line').click();
  assert.equal(env.rows.children.length, 2);
  [...env.rows.children].forEach(row => row.querySelector('.remove-row').click());
  await env.scan(special('EXPENSE'));
  const expense = env.rows.children[0];
  assert.equal(expense.querySelector('input[name="custom_unit_price"]').value, '0');
  assert.equal(expense.querySelector('input[name="custom_unit_price"]').readOnly, true);
  env.form.dataset.fixedSaleType = 'avito';
  expense.querySelector('input[name="custom_unit_cost"]').dispatchEvent({type: 'input'});
  assert.equal(env.commission.textContent.replace(/\s/g, ''), '0,00₽');
  await env.scan(special('EXPENSE'));
  assert.equal(env.rows.children.length, 2);
  await env.scan(special('DIGITAL_PRODUCT'));
  assert.equal(env.rows.children.length, 2);
  const normal = environment('sale');
  await normal.scan(normal.product(1));
  await normal.scan(special('DIGITAL_PRODUCT'));
  await normal.scan(special('EXPENSE'));
  assert.equal(normal.rows.children.length, 1);
  const bySearch = environment('sale');
  bySearch.form.querySelector('.add-stock-line').click();
  bySearch.autocomplete[0].onSelect(special('DIGITAL_PRODUCT'));
  assert.equal(bySearch.rows.children.length, 1, 'Выбор системной позиции убирает пустые обязательные строки');
  assert.equal(bySearch.rows.children[0].dataset.systemKind, 'DIGITAL_PRODUCT');

  // Остатки прихода обновляются без изменения количества, цены и выбранного товара.
  const supply = environment('supply');
  const item = {...supply.product(1), warehouse_stock: 5, storage_locations: 'A1-2-1\\2, A6-3'};
  await supply.scan(item);
  const supplyRow = supply.rows.children[0];
  assert.equal(supplyRow.querySelector('[data-supply-stock-reference]').textContent, 'На складе: 5 шт. (A1-2-1\\2, A6-3)');
  supplyRow.querySelector('input[name="quantity"]').value = '7';
  supplyRow.querySelector('input[name="purchase_unit_cost"]').value = '123.45';
  supply.setResults([{...item, warehouse_stock: 0, storage_locations: ''}]);
  const warehouse = supply.form.querySelector('[id="id_warehouse"]');
  warehouse.value = '2'; warehouse.dispatchEvent({type: 'change'});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(supplyRow.querySelector('[data-supply-stock-reference]').textContent, 'На складе: 0 шт. (место не указано)');
  assert.equal(supplyRow.querySelector('input[name="quantity"]').value, '7');
  assert.equal(supplyRow.querySelector('input[name="purchase_unit_cost"]').value, '123.45');
  assert.equal(supplyRow.children.length, 5, 'Подсказка не добавляет столбцы');

  // Общий компонент раскрывает три независимые секции и сбрасывается при новой загрузке.
  for (let reload = 0; reload < 2; reload++) {
    const contents = {};
    const buttons = ['stats-report-filters', 'stats-dynamics', 'stats-channels'].map(id => {
      contents[id] = {hidden: true};
      const attributes = {'aria-controls': id, 'aria-expanded': 'false'};
      return {getAttribute: key => attributes[key], setAttribute: (key, value) => {attributes[key] = value;}, addEventListener: function(event, callback) {this[event] = callback;}};
    });
    vm.runInNewContext(fs.readFileSync('static/js/app.js', 'utf8'), {
      window: {}, setInterval() {}, document: {addEventListener() {}, querySelector() {return null;},
        querySelectorAll: selector => selector === '[data-collapse-toggle]' ? buttons : [],
        getElementById: id => contents[id]},
    });
    assert(Object.values(contents).every(content => content.hidden));
    buttons[0].click(); assert.equal(contents['stats-report-filters'].hidden, false);
    assert.equal(contents['stats-dynamics'].hidden, true);
    buttons[1].click(); assert.equal(contents['stats-dynamics'].hidden, false);
    buttons[0].click(); assert.equal(contents['stats-report-filters'].hidden, true);
    assert.equal(contents['stats-dynamics'].hidden, false);
  }
  console.log('Системные позиции, запрет смешивания, отдельные строки, нулевая цена/комиссия расхода, подсказки прихода и сворачивание — OK.');
}
main().catch(error => {console.error(error); process.exitCode = 1;});
