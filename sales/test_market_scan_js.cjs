const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

let handler, openDialog = false, pending, nextId = 0;
const requests = [], observations = [], status = {textContent: ''};
const controls = {dataset: {marketScanUrl: '/sales/market-scan/'}};
const api = {
  requestId: () => 'scan-' + (++nextId),
  request: (url, options) => {
    assert.equal(url, controls.dataset.marketScanUrl);
    const record = {barcode: options.body.get('barcode'), id: options.body.get('request_id')};
    requests.push(record);
    return new Promise((resolve) => {pending = resolve;});
  },
  observe: async (job, display) => {observations.push(job.status_url); display('Стикер напечатан, заказ готов');},
};
vm.runInNewContext(fs.readFileSync('static/js/sale-market-scan.js', 'utf8'), {
  window: {GameBAT: {marketPrint: api, registerGlobalBarcodeHandler: (callback) => {handler = callback;}}},
  document: {getElementById: (id) => id === 'market-scan-controls' ? controls : status,
    querySelector: () => openDialog ? {} : null},
  FormData: class extends Map {constructor() {super();}},
});
const flush = () => new Promise((resolve) => setImmediate(resolve));
(async () => {
  openDialog = true; handler('0000000012345'); await flush(); assert.equal(requests.length, 0);
  openDialog = false;
  const first = handler('0000000012345');
  const second = handler('0000000054321');
  await flush(); assert.equal(requests.length, 1);
  assert.equal(requests[0].barcode, '0000000012345');
  pending({order_id: 123, scanned: 1, required: 2, complete: false});
  await first; await flush(); assert.equal(observations.length, 0);
  assert.equal(requests.length, 2);
  pending({order_id: 123, scanned: 2, required: 2, complete: true, print_job_id: 'job-1', status_url: '/jobs/1/'});
  await second; await flush(); assert.deepEqual(observations, ['/jobs/1/']);
  assert(status.textContent.includes('напечатан'));
  assert.notEqual(requests[0].id, requests[1].id);
  console.log('Market scan JS: registration, barcode leading zeros, serial scans, full composition and modal exclusion OK');
})().catch((error) => {console.error(error); process.exitCode = 1;});
