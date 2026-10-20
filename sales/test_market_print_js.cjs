const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function scenario({failed = false, network = false} = {}) {
  let submit, counter = 0, networkFailed = false;
  const requests = [], button = {disabled: false}, message = {textContent: ''};
  const form = {action: '/sales/7/market-print/', dataset: {},
    querySelector: (selector) => selector === 'button' ? button : message,
    setAttribute() {}, removeAttribute() {}};
  form.closest = () => form;
  const readyButton = {disabled: true}, current = {}, substatus = {};
  const ready = {dataset: {marketOrderNumber: '123', marketAction: 'ready'}, querySelector: (selector) =>
    selector === 'button' ? readyButton : (selector.includes('substatus') ? substatus : current)};
  const result = (state) => ({state, status_url: '/sales/market-print/test/', order_id: 123,
    market_status: 'PROCESSING', market_substatus: 'STARTED', printed: state === 'printed' || state === 'done',
    message: state === 'error' ? 'Windows print failed' : (state === 'done' ? 'Стикер напечатан' : state)});
  const replies = network ? [result('done')] : [result('pending'), result(failed ? 'error' : 'spooled'), result('printed'), result('done')];
  vm.runInNewContext(fs.readFileSync('static/js/sale-market-print.js', 'utf8'), {
    window: {GameBAT: {}, print() {throw Error('Browser print is forbidden');}, open() {throw Error('New pages are forbidden');}},
    document: {
      addEventListener: (event, callback) => {submit = callback;},
      querySelectorAll: () => [ready],
      createElement() {throw Error('PDF iframe is forbidden');},
    },
    crypto: {randomUUID: () => 'request-' + (++counter)},
    FormData: class extends Map {constructor(value) {super(); assert.equal(value, form);}},
    setTimeout: (callback) => queueMicrotask(callback),
    fetch: async (url, options) => {
      requests.push({url, id: options.body?.get('request_id'), options});
      if (network && !networkFailed) {networkFailed = true; throw new TypeError('Network failed');}
      return {ok: true, headers: {get: () => 'application/json'}, json: async () => replies.shift()};
    },
  });
  const event = {target: form, preventDefault() {}};
  const printing = submit(event);
  await submit(event);
  await printing;
  if (network) {
    assert.equal(form.dataset.printRequestId, 'request-1');
    await submit(event);
    assert.equal(requests[0].id, requests[1].id);
  }
  assert.equal(requests.filter(({options}) => options.method === 'POST').length, network ? 2 : 1);
  assert.equal(button.disabled, false);
  assert.equal(readyButton.disabled, failed);
  assert(message.textContent.includes(failed ? 'Windows print failed' : 'напечатан'));
  assert.equal(form.dataset.printRequestId, undefined);
  assert(!requests.some(({url}) => url.includes('/file/')));
}

(async () => {
  await scenario();
  await scenario({failed: true});
  await scenario({network: true});
  console.log('Native label print JS: no browser printing or pages, polling to printed, error recovery and idempotent network retry OK');
})().catch((error) => {console.error(error); process.exitCode = 1;});
