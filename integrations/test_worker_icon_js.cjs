// Проверка трёх состояний индикатора реальным скриптом без сети и звука.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const template = fs.readFileSync('templates/base.html', 'utf8');
assert.match(template, /<svg class="worker-start-icon"[^>]+viewBox="0 0 24 24"/);
assert.match(template, /<span class="worker-error-icon" aria-hidden="true">!<\/span>/);
assert.ok(!template.includes('⏻'));
const source = fs.readFileSync('static/js/worker-monitoring.js', 'utf8');

async function check(mode, fails = false) {
  const icon = {
    hidden: true, dataset: {}, attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; },
    querySelector() { throw new Error('Индикатор не должен переписывать SVG текстовым глифом'); },
  };
  const audioStatus = {textContent: ''}, feedStatus = {textContent: ''};
  const root = {dataset: {user: 'test', statusUrl: '/fake-status', soundUrl: '/fake-audio'},
    querySelector: selector => selector === '[data-worker-audio-status]' ? audioStatus : feedStatus};
  const document = {
    querySelector: selector => selector === '[data-worker-monitor]' ? root
      : selector === '[data-worker-alert]' ? icon : null,
    querySelectorAll: () => [], addEventListener() {},
  };
  let audioPlayed = 0;
  const context = {
    document, AbortController, setTimeout: () => 1, clearTimeout() {},
    Audio: class { constructor() { this.dataset = {}; } pause() {} play() { audioPlayed++; return Promise.resolve(); } },
    window: {addEventListener() {}, GameBAT: {
      notificationSound: {register: () => () => {}},
      marketAlertState: {IndexedState: class { enabled() { return Promise.resolve(false); } }},
    }},
    fetch: async () => {
      if (fails) throw new Error('Synthetic status failure');
      return {ok: true, redirected: false, json: async () => ({
        alarm: mode === 'error', starting: mode === 'starting', incidents: [], services: [],
        server_time: new Date().toISOString(), controller_label: 'Тестовый контроллер',
        mode: 'managed', running_count: 0, stopped_count: 0, disabled_count: 0,
      })};
    },
  };
  vm.runInNewContext(source, context);
  await new Promise(resolve => setImmediate(resolve));
  const expected = fails ? 'starting' : mode;
  assert.equal(icon.dataset.state, expected);
  assert.equal(icon.hidden, expected === 'healthy');
  assert.equal(icon.attributes['aria-label'], icon.title);
  assert.ok(icon.title.length > 0);
  assert.equal(audioPlayed, 0);
}

(async () => {
  for (const mode of ['starting', 'error', 'healthy']) await check(mode);
  await check('error', true);
  console.log('Worker indicator: SVG, startup/error/healthy, unavailable feed and silent disabled audio: OK');
})().catch(error => { console.error(error); process.exitCode = 1; });
