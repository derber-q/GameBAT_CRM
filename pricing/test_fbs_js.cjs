// Проверяет предпросмотр, подтверждение применения и сохранение новых правок.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const result = {
  ok: true, final_price: '9007199254740993', actual_profit: '500.01', desired_profit: '500.00',
  cost_price: '1300.00', raw_volume_l: '0.442', billing_volume_l: '1', weight_g: 140,
  placement_fee: '300.00', tax_fee: '100.00', payment_transfer_fee: '20.00', delivery_fee: '50.00',
  middle_mile_fee: '92.00', packaging_fee: '30.00', fixed_payment_fee: '0.00', other_fbs_fee: '0.00',
};
const node = () => ({textContent: '', children: [], appendChild(item) { this.children.push(item); },
  replaceChildren() { this.children = []; }});
const output = () => {
  const fields = Object.fromEntries(['price', 'profit-result', 'volume', 'breakdown', 'save-status']
    .map((name) => [`[data-fbs-${name}]`, node()]));
  return {fields, querySelector(selector) { return fields[selector] || null; }};
};
const editor = output();
const inline = output();
const dimensionsButton = {hidden: false};
const inlineFields = {hidden: true};
inline.fields['[data-fbs-dimensions-open]'] = dimensionsButton;
inline.fields['[data-fbs-inputs]'] = inlineFields;
const events = {};
const profit = {name: 'yandex_desired_profit', value: '500.00', type: 'number'};
const version = {name: 'version', value: 'v1', type: 'hidden'};
let focusedDimension;
const sizes = ['length_cm', 'width_cm', 'height_cm'].map((name) => ({
  name, value: name === 'width_cm' ? '' : '20', type: 'number',
  focus() { focusedDimension = name; },
}));
const elements = [profit, version, ...sizes];
elements.namedItem = (name) => elements.find((item) => item.name === name);
const form = Object.assign(editor, {
  dataset: {previewUrl: '/preview', productPriceForm: 'row-form', inlineProfitSnapshot: '200.00'},
  action: '/save', elements, isConnected: true,
  addEventListener(name, handler) { events[name] = handler; },
});
const sourceProfit = {value: '200.00', closest() { return inline; }};
const sourcePrice = {value: '3990.00', hidden: true, dispatchEvent() {}};
const row = {querySelector(selector) {
  if (selector === '[data-fbs-profit]') return sourceProfit;
  if (selector === '[data-fbs-inline]') return inline;
  if (selector === '[name="yandex_market_price"]' || selector === '[data-price-field="yandex_market_price"]') return sourcePrice;
  return null;
}};
inline.closest = () => row;
const sourceForm = {closest() { return row; }};
const openEvents = {};
const dimensionsLink = {
  href: '/detail', closest(selector) { return selector === '[data-price-row]' ? row : inline; },
  hasAttribute(name) { return name === 'data-fbs-dimensions-open'; },
  addEventListener(name, handler) { openEvents[name] = handler; },
};
const dialogContent = {textContent: '', innerHTML: '', querySelector() { return form; },
  querySelectorAll() { return [form]; }, replaceChildren() {}};
let dialogOpened = false;
const dialog = {
  querySelector(selector) { return selector === '[data-fbs-close]' ? {addEventListener() {}} : dialogContent; },
  showModal() { dialogOpened = true; }, close() {}, addEventListener() {},
};
class FormDataMock {
  constructor(target) { this.data = new Map((target?.elements || []).filter((item) => !item.disabled).map((item) => [item.name, item.value])); }
  set(name, value) { this.data.set(name, value); }
  get(name) { return this.data.get(name); }
}
let confirmed = false, requests = [], pendingSave, versionNumber = 1, dimensionsComplete = true, sourceFormAvailable = true;
const context = {
  document: {
    visibilityState: 'visible', querySelectorAll(selector) {
      if (selector === '[data-fbs-form]') return [form];
      if (selector === '[data-fbs-open]') return [dimensionsLink];
      return [];
    },
    getElementById(id) { return id === 'row-form' ? (sourceFormAvailable ? sourceForm : null) : id === 'fbs-pricing-dialog' ? dialog : null; }, createElement: node,
  },
  window: {confirm() { return confirmed; }}, FormData: FormDataMock, AbortController, Event,
  setInterval() { return 1; }, clearInterval() {}, setTimeout() { return 1; }, clearTimeout() {},
  fetch: async (url, options) => {
    requests.push({url, data: options.body});
    if (url === '/save' && pendingSave) await pendingSave;
    return {ok: true, redirected: false, async text() { return '<form></form>'; },
      headers: {get() { return 'application/json'; }}, async json() {
      return url === '/save' ? {ok: true, calculation: result, version: `v${++versionNumber}`,
        dimensions_complete: dimensionsComplete,
        applied_price: options.body.get('action') === 'apply' ? '4890.00' : null, message: 'Сохранено'} : result;
    }};
  },
};
const submit = (action) => events.submit({preventDefault() {}, submitter: {value: action}});
const tick = () => new Promise(setImmediate);

(async () => {
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/js/fbs-pricing.js'), 'utf8'), context);
  await tick();
  assert.match(editor.fields['[data-fbs-price]'].textContent, /9 007 199 254 740 993 ₽/);
  assert.match(editor.fields['[data-fbs-volume]'].textContent, /0\.442 л/);
  assert.equal(editor.fields['[data-fbs-breakdown]'].children.length, 12);

  inline.fields['[data-fbs-profit]'] = sourceProfit;
  await openEvents.click({preventDefault() {}});
  assert.equal(dialogOpened, true, 'Кнопка размеров открывает окно ввода');
  assert.equal(focusedDimension, 'width_cm', 'Фокус получает первый отсутствующий размер');
  profit.value = '500.00';

  const before = requests.length;
  await submit('apply');
  assert.equal(requests.length, before, 'Отмена подтверждения не отправляет запрос');
  confirmed = true;
  await submit('apply');
  assert.equal(sourcePrice.value, '4890.00');
  assert.equal(sourceProfit.value, '500.00');
  assert.equal(version.value, 'v2');
  assert.equal(dimensionsButton.hidden, true, 'После сохранения размеров кнопка скрывается');
  assert.equal(inlineFields.hidden, false, 'При заполненных размерах поля расчёта видны');
  assert.equal(sourcePrice.hidden, false, 'Поле цены появляется без перезагрузки');

  profit.value = '600.00';
  await submit('save');
  assert.equal(sourceProfit.value, '600.00', 'Повторное сохранение обновляет значение в таблице');
  assert.equal(sourcePrice.value, '4890.00', 'Обычное сохранение не применяет цену');

  let release;
  pendingSave = new Promise((resolve) => { release = resolve; });
  profit.value = '700.00';
  const saving = submit('save');
  await tick();
  const savingRequests = requests.length;
  await submit('save');
  assert.equal(requests.length, savingRequests, 'Повторный клик во время сохранения игнорируется');
  profit.value = '800.00';
  sourceProfit.value = '900.00';
  release();
  await saving;
  assert.equal(profit.value, '800.00');
  assert.equal(sourceProfit.value, '900.00', 'Новые правки в таблице не перезаписываются');
  assert.match(editor.fields['[data-fbs-save-status]'].textContent, /несохранённые изменения/);
  assert.equal(version.value, 'v4');
  pendingSave = null;
  dimensionsComplete = false;
  sourceFormAvailable = false;
  await submit('save');
  assert.equal(dimensionsButton.hidden, false, 'При очистке размера кнопка возвращается и без формы редактирования цен');
  assert.equal(inlineFields.hidden, true);
  assert.equal(sourcePrice.hidden, true);
  assert.equal(sourcePrice.value, '4890.00', 'Скрытие поля сохраняет ранее указанную цену');
  console.log('FBS JS: точные денежные строки, объём, детализация, подтверждение, повторное сохранение и новые правки OK');
})().catch((error) => { console.error(error); process.exitCode = 1; });
