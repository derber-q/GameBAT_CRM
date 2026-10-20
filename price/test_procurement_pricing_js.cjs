const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function field(value = '', readOnly = false) {
  const classes = () => ({values: new Set(), toggle(name, active) { active ? this.values.add(name) : this.values.delete(name); }});
  return {
    value, readOnly, disabled: false, validationMessage: '', events: {},
    classList: classes(), parentElement: {classList: classes()},
    setCustomValidity(message) { this.validationMessage = message; },
    addEventListener(name, callback) { this.events[name] = callback; },
    enter(value) { this.value = value; this.events.input(); },
  };
}
function environment(specifications = [{}]) {
  const rows = specifications.map((spec, index) => {
    const fields = {
      markup: field(spec.markup ?? '100.00', spec.readOnly ?? false),
      delivery: field(spec.delivery ?? '35.00'),
      prepayment: field(spec.prepayment ?? '1135.00', spec.readOnly ?? false),
      postpayment: field(spec.postpayment ?? '1195.00', spec.readOnly ?? false),
      'postpayment-surcharge': field(spec.surcharge ?? '60.00', spec.readOnly ?? false),
      'price-source': field('markup'),
      'price-error': {textContent: ''},
      'effective-markup': {textContent: ''},
      'prepayment-rounding': {textContent: ''},
      'postpayment-rounding': {textContent: ''},
    };
    return {fields, dataset: {base: spec.base ?? '1000.00', itemId: String(index + 1), surchargeMode: spec.mode ?? 'tiered'},
      querySelector(selector) { return fields[selector.slice(6, -1)]; }};
  });
  const payload = field();
  payload.disabled = true;
  const confirmed = field();
  confirmed.disabled = true;
  const buttons = {'negative-cancel': field(), 'negative-accept': field(), 'negative-count': {textContent: ''}};
  const dialog = {
    open: false, showModal() { this.open = true; }, close() { this.open = false; },
    querySelector(selector) { return buttons[selector.slice(6, -1)]; },
  };
  const inputs = rows.flatMap(row => Object.values(row.fields).filter(value => 'value' in value));
  const form = {
    events: {},
    querySelector(selector) { return selector === '[data-pricing-rows]' ? payload : confirmed; },
    querySelectorAll(selector) {
      if (selector === '[data-markup]') return rows.map(row => row.fields.markup);
      return selector.endsWith(' input') ? inputs : rows;
    },
    addEventListener(name, callback) { this.events[name] = callback; },
    requestSubmit() { this.events.submit({preventDefault() {}}); },
  };
  const document = {
    addEventListener(name, callback) { if (name === 'DOMContentLoaded') callback(); },
    querySelectorAll(selector) { return selector === '.procurement-pricing-form' ? [form] : rows; },
    querySelector() { return dialog; },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/js/procurement-pricing.js'), 'utf8'), {document});
  return {rows, form, payload, inputs, dialog, buttons, confirmed};
}

const env = environment([{}, {}]);
const fields = env.rows[0].fields;
for (const [value, markup, postpayment] of [
  ['1999.99', '964.99', '2060.00'], ['2000', '965.00', '2080.00'],
  ['2999.99', '1964.99', '3080.00'], ['3000', '1965.00', '3100.00'],
]) {
  fields.prepayment.enter(value);
  assert.equal(fields.prepayment.value, value);
  assert.equal(fields.markup.value, markup);
  assert.equal(fields.postpayment.value, postpayment);
  assert.equal(fields['price-source'].value, 'prepayment');
}
for (const [value, prepayment, markup] of [
  ['2059.99', '2000.00', '964.99'], ['2080', '2000.00', '965.00'],
  ['2060', '2000.00', '964.99'], ['3080', '3000.00', '1964.99'],
  ['3079.99', '3000.00', '1964.99'], ['3100', '3000.00', '1965.00'],
]) {
  fields.postpayment.enter(value);
  assert.equal(fields.postpayment.value, value);
  assert.equal(fields.prepayment.value, prepayment);
  assert.equal(fields.markup.value, markup);
  assert.equal(fields['price-source'].value, 'postpayment');
}
for (const value of ['59.99', '2070', '2079.99', '3090', '3099.99']) {
  fields.postpayment.enter(value);
  assert.notEqual(fields.postpayment.validationMessage, '');
  assert.notEqual(fields['price-error'].textContent, '');
  assert.equal(fields.prepayment.value, '3000.00');
}
fields.postpayment.enter('2080');
assert.equal(fields.postpayment.validationMessage, '');
assert.equal(fields['price-error'].textContent, '');
fields.delivery.enter('100');
assert.equal(fields.prepayment.value, '2070.00');
assert.equal(fields.postpayment.value, '2150.00');
assert.equal(fields['price-source'].value, 'markup');
fields.markup.enter('0.01');
assert.equal(fields.prepayment.value, '1110.00');
assert.equal(fields.postpayment.value, '1170.00');
for (const value of ['', '-1', 'NaN', 'Infinity', '1.001', '1e3']) {
  fields.prepayment.enter(value);
  assert.notEqual(fields.prepayment.validationMessage, '');
  assert.equal(fields.markup.value, '0.01');
}
fields.prepayment.enter('1099.99');
assert.equal(fields.prepayment.validationMessage, '');
assert.equal(fields.markup.value, '-0.01');
assert.ok(fields.markup.classList.values.has('danger-text'));
assert.ok(fields.markup.parentElement.classList.values.has('field-error'));
fields.prepayment.enter('2000.01');
assert.equal(fields.markup.value, '900.01');
assert.ok(!fields.markup.classList.values.has('danger-text'));
assert.equal(env.rows[1].fields.markup.value, '100.00');

const exact = environment([{base: '0.10', delivery: '0.20'}]).rows[0].fields;
exact.markup.enter('0.10');
assert.equal(exact.prepayment.value, '10.00');
assert.equal(exact.postpayment.value, '70.00');
exact.prepayment.enter('0,41');
assert.equal(exact.markup.value, '0.11');

const large = environment([{base: '9999999999999900.01', delivery: '0.01'}]).rows[0].fields;
large.markup.enter('0.01');
assert.equal(large.prepayment.value, '9999999999999910.00');
assert.equal(large.postpayment.value, '10000000000000010.00');
large.prepayment.enter('999999999999999999.99');
assert.match(large.prepayment.validationMessage, /превышает/);

const locked = environment([{readOnly: true}]).rows[0].fields;
locked.prepayment.enter('2000');
assert.equal(locked.markup.value, '100.00');
locked.delivery.enter('50');
assert.equal(locked.prepayment.value, '1150.00');
assert.equal(locked.postpayment.value, '1210.00');

env.form.events.submit();
assert.equal(env.payload.disabled, false);
const rows = JSON.parse(env.payload.value);
assert.equal(rows['1'].price_source, 'prepayment');
assert.equal(rows['1'].prepayment, '2000.01');
assert.equal(rows['1'].markup, '900.01');
assert.equal(Object.keys(rows).length, 2);
assert.equal(rows['1'].postpayment_surcharge, '80.00');
assert.equal(rows['1'].surcharge_mode, 'tiered');
assert.ok(env.inputs.every(input => input.disabled));
console.log('Пересчёт предоплаты, постоплаты, наценки, проверки сумм и отправка JSON: OK');

const negative = environment([{markup: '-0.01'}]);
const negativeFields = negative.rows[0].fields;
assert.ok(negativeFields.markup.classList.values.has('danger-text'));
negativeFields.markup.enter('-35.01');
assert.equal(negativeFields.prepayment.value, '1000.00');
assert.equal(negativeFields.postpayment.value, '1060.00');
let prevented = false;
negative.form.events.submit({preventDefault() { prevented = true; }});
assert.ok(prevented);
assert.ok(negative.dialog.open);
assert.equal(negative.payload.disabled, true);
assert.ok(negative.inputs.every(input => !input.disabled));
negative.buttons['negative-cancel'].events.click();
assert.ok(!negative.dialog.open);
assert.equal(negative.confirmed.value, '');
negative.form.events.submit({preventDefault() {}});
negative.buttons['negative-accept'].events.click();
assert.ok(!negative.dialog.open);
assert.equal(negative.confirmed.value, 'true');
assert.equal(negative.confirmed.disabled, false);
assert.equal(JSON.parse(negative.payload.value)['1'].markup, '-35.01');
negative.form.events.input();
assert.equal(negative.confirmed.value, '');
assert.equal(negative.confirmed.disabled, true);
const belowZero = environment().rows[0].fields;
belowZero.markup.enter('-1035.01');
assert.match(belowZero.markup.validationMessage, /не может быть отрицательной/);
console.log('Отрицательная наценка: красное поле, подтверждение, отмена и сброс подтверждения: OK');

for (const value of ['0', '0.00', '0,00', '-0.00']) {
  const zero = environment([{markup: value, prepayment: '1035.00', postpayment: '1095.00'}]);
  const zeroFields = zero.rows[0].fields;
  assert.ok(zeroFields.markup.classList.values.has('danger-text'));
  assert.ok(zeroFields.markup.parentElement.classList.values.has('field-error'));
  zeroFields.markup.enter('0.01');
  assert.ok(!zeroFields.markup.classList.values.has('danger-text'));
  assert.ok(!zeroFields.markup.parentElement.classList.values.has('field-error'));
  zeroFields.prepayment.enter('1035.00');
  assert.equal(zeroFields.markup.value, '0.00');
  assert.ok(zeroFields.markup.classList.values.has('danger-text'));
  assert.ok(zeroFields.markup.parentElement.classList.values.has('field-error'));
  zero.form.events.submit({preventDefault() { assert.fail('Нулевая наценка не требует подтверждения'); }});
  assert.ok(!zero.dialog.open);
  assert.equal(JSON.parse(zero.payload.value)['1'].markup, '0.00');
}
console.log('Нулевая наценка: красное поле при открытии и пересчёте, сохранение без подтверждения: OK');

const fixed = environment([{mode: 'fixed', surcharge: '500.00'}]);
const fixedFields = fixed.rows[0].fields;
fixedFields.prepayment.enter('2000');
assert.equal(fixedFields.postpayment.value, '2500.00');
fixedFields.postpayment.enter('2060');
assert.equal(fixedFields.prepayment.value, '1560.00');
assert.equal(fixedFields.markup.value, '525.00');
assert.equal(fixedFields.postpayment.validationMessage, '');
fixedFields['postpayment-surcharge'].enter('250.25');
assert.equal(fixedFields.prepayment.value, '1560.00');
assert.equal(fixedFields.postpayment.value, '1820.00');
assert.equal(fixedFields.markup.value, '525.00');
fixedFields.postpayment.enter('250');
assert.match(fixedFields.postpayment.validationMessage, /меньше доплаты/);
for (const value of ['', '-1', '1.001', 'NaN']) {
  fixedFields['postpayment-surcharge'].enter(value);
  assert.notEqual(fixedFields['postpayment-surcharge'].validationMessage, '');
}
fixedFields['postpayment-surcharge'].enter('0');
assert.equal(fixedFields.postpayment.value, fixedFields.prepayment.value);
const cdOverride = environment().rows[0];
cdOverride.fields['postpayment-surcharge'].enter('125');
assert.equal(cdOverride.dataset.surchargeMode, 'fixed');
cdOverride.fields.prepayment.enter('3000');
assert.equal(cdOverride.fields.postpayment.value, '3130.00');
console.log('Фиксированная доплата Tech, ручная ставка, обратный расчёт и переопределение CD: OK');

const independent = environment([{base: '2800.00', markup: '201.00', delivery: '0.00', mode: 'fixed', surcharge: '126.00'}]).rows[0].fields;
for (let repeat = 0; repeat < 2; repeat += 1) {
  independent.markup.enter('201.00');
  assert.equal(independent.prepayment.value, '3010.00');
  assert.equal(independent.postpayment.value, '3130.00');
  assert.equal(independent['effective-markup'].textContent, '210.00');
  assert.equal(independent['prepayment-rounding'].textContent, '9.00');
  assert.equal(independent['postpayment-rounding'].textContent, '3.00');
  assert.equal(independent['postpayment-surcharge'].value, '126.00');
}
console.log('Независимое округление и сохранение исходной наценки и доплаты: OK');
