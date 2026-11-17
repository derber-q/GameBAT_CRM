const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const played = [];
let denied = false;
const status = {hidden: true};
const window = {GameBAT: {existing: true}};
vm.runInNewContext(fs.readFileSync('static/js/barcode-feedback.js', 'utf8'), {
  window, document: {body: {dataset: {barcodeYesSound: '/yes.mp3', barcodeNoSound: '/no.mp3'}},
    querySelector: selector => selector === '[data-barcode-audio-status]' ? status : null},
  Audio: class {
    constructor(url) {this.url = url; this.dataset = {};}
    play() {
      played.push(this.url);
      if (denied) return Promise.reject(Object.assign(new Error(), {name: 'NotAllowedError'}));
      queueMicrotask(() => this.onended());
      return Promise.resolve();
    }
    pause() {}
  },
  setTimeout, clearTimeout,
});
(async () => {
  assert.equal(await window.GameBAT.playBarcodeFeedback(true), true);
  assert.equal(await window.GameBAT.playBarcodeFeedback(false), true);
  assert.deepEqual(played, ['/yes.mp3', '/no.mp3']);
  assert.equal(window.GameBAT.existing, true);
  denied = true;
  assert.equal(await window.GameBAT.playBarcodeFeedback(true), false);
  assert.equal(status.hidden, false);
  console.log('Barcode feedback: success, refusal and browser denial do not break the operation — OK');
})().catch(error => {console.error(error); process.exitCode = 1;});
