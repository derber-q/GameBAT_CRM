const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const handlers = {}, dialogHandlers = {};
let open = false, submissions = 0, sentOrder;
const dialog = {
  addEventListener: (event, callback) => {dialogHandlers[event] = callback;},
  showModal: () => {open = true;},
  close: () => {open = false; dialogHandlers.close?.();},
};
const question = {textContent: ''};
const dialogForm = {addEventListener: (event, callback) => {handlers['confirm:' + event] = callback;}};
const back = {addEventListener: (event, callback) => {handlers['back:' + event] = callback;}};
const elements = {'sale-market-cancel-dialog': dialog, 'sale-market-cancel-confirm-form': dialogForm,
  'sale-market-cancel-question': question, 'sale-market-cancel-back': back};
const confirmation = {value: ''};
const cancelForm = {
  dataset: {marketAction: 'cancel', marketOrderNumber: '123'},
  querySelector: () => confirmation,
  submit() {submissions++; sentOrder = this.dataset.marketOrderNumber; assert.equal(confirmation.value, 'yes');},
};
cancelForm.closest = () => cancelForm;
const readyForm = {dataset: {marketAction: 'ready'}};
readyForm.closest = () => readyForm;
const submitEvent = (target) => ({target, prevented: false, preventDefault() {this.prevented = true;}});
vm.runInNewContext(fs.readFileSync('static/js/sale-market-actions.js', 'utf8'), {
  document: {getElementById: (id) => elements[id], addEventListener: (event, callback) => {handlers[event] = callback;}},
});

const ready = submitEvent(readyForm);
handlers.submit(ready);
assert.equal(ready.prevented, false);
assert.equal(open, false);
let cancel = submitEvent(cancelForm);
handlers.submit(cancel);
assert(cancel.prevented);
assert(open);
assert(question.textContent.includes('123'));
assert.equal(submissions, 0);
handlers['back:click']();
handlers['confirm:submit'](submitEvent(dialogForm));
assert.equal(submissions, 0);
assert.equal(open, false);
handlers.submit(submitEvent(cancelForm));
dialogHandlers.cancel();
handlers['confirm:submit'](submitEvent(dialogForm));
assert.equal(submissions, 0);
cancelForm.dataset.marketOrderNumber = '456';
handlers.submit(submitEvent(cancelForm));
handlers['confirm:submit'](submitEvent(dialogForm));
handlers['confirm:submit'](submitEvent(dialogForm));
assert.equal(submissions, 1);
assert.equal(sentOrder, '456');
assert.equal(open, false);
handlers.submit(submitEvent(cancelForm));
assert(open);
assert.equal(confirmation.value, '');
console.log('Market actions JS: ready without confirmation, cancel/back/Escape, scoped confirmation, double submit and repeated cancellation OK');
