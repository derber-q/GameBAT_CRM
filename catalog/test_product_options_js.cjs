const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function fixture(value = '1', disabled = false) {
  const choice = {value, disabled, addEventListener(_event, callback) { this.change = callback; }};
  const custom = {required: false, disabled};
  const wrap = {hidden: false};
  const block = {querySelector(selector) {
    return {'[data-newness-duration]': choice, '[data-newness-custom]': custom, '[data-newness-custom-wrap]': wrap}[selector];
  }};
  const document = {addEventListener(_event, callback) { callback(); }, querySelectorAll() {
    return [{querySelector() { return null; }}, block];
  }};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/js/product-options.js'), 'utf8'), {document});
  return {choice, custom, wrap};
}

const form = fixture();
assert.ok(form.wrap.hidden);
assert.ok(form.custom.disabled);
form.choice.value = 'custom';
form.choice.change();
assert.equal(form.wrap.hidden, false);
assert.ok(form.custom.required);
assert.equal(form.custom.disabled, false);
form.choice.value = '0';
form.choice.change();
assert.ok(form.wrap.hidden);
assert.equal(form.custom.required, false);
assert.ok(form.custom.disabled);
const readonly = fixture('custom', true);
assert.equal(readonly.wrap.hidden, false);
assert.ok(readonly.custom.disabled);
assert.equal(readonly.custom.required, false);
console.log('Выбор календарного срока новинки, собственный срок и режим чтения: OK');
