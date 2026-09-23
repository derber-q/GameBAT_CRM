const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
// Execute the complete shared script: filter initialization must not prevent
// collapse handlers (or the scanner API) from being installed.
for (const withSeries of [false, true]) {
  const control = () => ({value: '', disabled: false, addEventListener() {}});
  const fields = {platform: control(), brand: control(), product_type: control()};
  if (withSeries) fields.game_series = control();
  const form = {querySelector(selector) {
    const match = selector.match(/data-product-filter="([^"]+)"/);
    return match ? fields[match[1]] || null : null;
  }};
  const contents = {};
  const buttons = ['parent', 'child', 'sibling'].map(id => {
    contents[id] = {hidden: false};
    const attrs = {'aria-controls': id, 'aria-expanded': 'true'};
    return {getAttribute: key => attrs[key], setAttribute: (key, value) => attrs[key] = value,
      addEventListener(event, handler) {this[event] = handler;}};
  });
  const window = {};
  vm.runInNewContext(fs.readFileSync('static/js/app.js', 'utf8'), {
    window, setInterval() {},
    document: {
      addEventListener() {}, querySelector() {return null;},
      getElementById(id) {return contents[id] || null;},
      querySelectorAll(selector) {
        if (selector === '[data-product-filters]') return [form];
        if (selector === '[data-collapse-toggle]') return buttons;
        return [];
      },
    },
  });
  assert.equal(typeof window.GameBAT.registerGlobalBarcodeHandler, 'function');
  buttons[1].click();
  assert.equal(contents.child.hidden, true);
  buttons[0].click();
  assert.equal(contents.parent.hidden, true);
  assert.equal(contents.sibling.hidden, false);
  assert.equal(buttons[0].getAttribute('aria-expanded'), 'false');
  buttons[0].click();
  assert.equal(contents.parent.hidden, false);
  assert.equal(contents.child.hidden, true);
  buttons[1].click();
  assert.equal(contents.child.hidden, false);
  assert.equal(buttons[1].getAttribute('aria-expanded'), 'true');
}
console.log('Collapse regression tests passed with and without game-series filter.');
