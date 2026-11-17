const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/avito-alert-sound.js', 'utf8');
const storage = new Map([['resource.avito.sound.v1', 'true']]);
const base = Date.parse('2026-11-16T12:00:00Z');
let plays = 0, lock = Promise.resolve();
function tab() {
  const status = {textContent: '', classList: {add() {}, remove() {}}};
  const root = {dataset: {soundUrl: '/static/audio/avito-action-notification.mp3'}, querySelector: () => status};
  const window = {GameBAT: {notificationSound: {register: () => () => {}}}, addEventListener() {}};
  vm.runInNewContext(source, {
    window, document: {querySelector: () => root},
    localStorage: {getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value)},
    navigator: {locks: {request: (_name, callback) => {const next = lock.then(callback); lock = next.catch(() => {}); return next;}}},
    Audio: class {
      constructor(url) {assert.equal(url, root.dataset.soundUrl); this.dataset = {};}
      play() {plays++; queueMicrotask(() => this.onended()); return Promise.resolve();}
      pause() {}
    },
    Date, Math, setTimeout, clearTimeout,
  });
  return window.GameBAT.avitoAlertSound;
}
const snapshot = (seconds, keys) => ({count: keys.length, action_keys: keys,
  observed_at: new Date(base + seconds * 1000).toISOString()});
(async () => {
  const first = tab(), second = tab();
  await first.observe(snapshot(0, ['1:publish']));
  await first.observe(snapshot(299, ['1:publish']));
  assert.equal(plays, 0); // исходный список и запуск страницы молчат
  await Promise.all([first.observe(snapshot(300, ['1:publish'])), second.observe(snapshot(300, ['1:publish']))]);
  assert.equal(plays, 1); // один повтор на все вкладки
  await first.observe(snapshot(315, ['1:publish']));
  assert.equal(plays, 1);
  await first.observe(snapshot(360, ['2:publish']));
  assert.equal(plays, 2); // новая позиция при том же количестве озвучивается сразу
  const reloaded = tab();
  await reloaded.observe(snapshot(659, ['2:publish']));
  assert.equal(plays, 2); // перезагрузка не сбрасывает срок
  await reloaded.observe(snapshot(660, ['2:publish']));
  assert.equal(plays, 3);
  await first.observe(snapshot(700, []));
  await first.observe(snapshot(1500, []));
  assert.equal(plays, 3); // после выполнения всех действий повторов нет
  await first.observe(snapshot(1600, ['3:publish']));
  assert.equal(plays, 4);
  await first.observe(snapshot(1501, ['old:publish']));
  assert.equal(plays, 4); // запоздалый снимок не поднимает старые действия
  storage.set('resource.avito.sound.v1', 'false');
  await first.observe(snapshot(2000, ['3:publish']));
  assert.equal(plays, 4);
  console.log('Avito: 5 minute repeat, new actions, shared tabs, reload, empty list and permission — OK');
})().catch(error => {console.error(error); process.exitCode = 1;});
