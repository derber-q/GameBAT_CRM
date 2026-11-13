const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const context = vm.createContext({URL, console});
for (const name of ['protocol.js','cards.js']) vm.runInContext(fs.readFileSync(path.join(__dirname,name),'utf8'),context);
function card(old, current, meta) {
  return {querySelector(selector) {
    if (selector.includes('old-price-value')) return old === undefined ? null : typeof old === 'object' ? old : {textContent:old};
    if (selector.includes('item-price-value')) return current === undefined ? null : {textContent:current};
    return selector.includes('[itemprop') && meta !== undefined ? {getAttribute:()=>meta} : null;
  }, querySelectorAll:()=>[]};
}
const price = context.ResourceAvitoCards.originalPrice;
assert.equal(price(card('5\u00a0890\u00a0₽','5 789 ₽','5789')),'5890');
assert.equal(price(card('5 890,50 ₽','5 789 ₽')),'5890.50');
assert.equal(price(card('1\u200e\u00a0890\u200b ₽\u2060','1 887 ₽')),'1890');
assert.equal(price(card('1 890 ₽ −3 ₽ бонусами','1 887 ₽')),'1890');
assert.equal(price(card('1 890 ₽ -3 с бонусами','1 887 ₽')),'1890');
assert.equal(price(card('１ ８９０ ₽','1 887 ₽')),'1890');
assert.equal(price(card({textContent:'',getAttribute:name=>name==='content'?'1890':null},'1 887 ₽')),'1890');
assert.equal(price(card({textContent:'',getAttribute:name=>name==='aria-label'?'Цена без скидки: 1 890 рублей':null},'1 887 ₽')),'1890');
assert.equal(price(card(undefined,'3 990 ₽','4000')),'3990');
assert.equal(price(card(undefined,undefined,'999999999999999999.99')),'999999999999999999.99');
for (const old of ['Уточняйте','от 100 ₽','0 ₽','-100 ₽','100 и 200 ₽','100 ₽ 200 ₽']) {
  assert.equal(price(card(old,'100 ₽','100')),null,old);
}
assert.equal(price(card(undefined,'от 100 ₽','100')),null);
assert.equal(price(card()),null);
const compare = context.ResourceAvitoCards.comparison;
assert.equal(compare('3399','3400'),'lower');
assert.equal(compare('3450','3400'),'higher');
assert.equal(compare('3400.00','3400'),'equal');
assert.equal(compare('3399,99','3400'),'lower');
assert.equal(compare('999999999999999999.98','999999999999999999.99'),'lower');
for (const minimum of ['', '0', 'abc', '-100', '1.234']) assert.equal(compare('3399',minimum),'');
assert.equal(compare(null,'3400'),'');
const reject = context.ResourceAvitoCards.conditionReason;
for (const name of [
  'PS5 GTA V Б/У', 'PS5 GTA V бу', 'PS5 GTA V б. у.', 'PS5 GTA V б\\у',
  'PS5 GTA V б-у', 'PS5 GTA V B/U', 'PS5 GTA V б/y', 'PS5 GTA V 6/у',
  'PS5 GTA V бэушный', 'PS5 GTA V подержанный', 'PS5 GTA V с рук',
  'PS5 GTA V как новый', 'PS5 GTA V почти новый', 'PS5 GTA V состояние нового',
  'PS5 GTA V не новый', 'PS5 GTA V вскрыт', 'PS5 GTA V новый, вскрыт для проверки',
  'PS5 GTA V вскрытая упаковка', 'PS5 GTA V распечатанный', 'PS5 GTA V распакован',
  'PS5 GTA V без плёнки', 'PS5 GTA V без заводской пленки', 'PS5 GTA V снята плёнка',
  'PS5 GTA V плёнка порвана', 'PS5 GTA V помята коробка', 'PS5 GTA V надрыв упаковки',
  'PS5 GTA V без слюды', 'PS5 GTA V без целлофана', 'PS5 GTA V дефект',
  'PS5 GTA V дефектный', 'PS5 GTA V брак', 'PS5 GTA V с царапинами',
  'PS5 GTA V микроцарапины', 'PS5 GTA V потёртости', 'PS5 GTA V трещина',
  'PS5 GTA V коцки', 'PS5 GTA V не читается', 'PS5 GTA V на запчасти',
  'PS5 GTA V уценка', 'PS5 GTA V уценённый', 'PS5 GTA V витринный образец',
  'PS5 GTA V восстановленный', 'PS5 GTA V после ремонта', 'PS5 GTA V перезапечатан',
  'PS5 GTA V использованный', 'PS5 GTA V пройден', 'PS5 GTA V один запуск',
  'PS5 GTA V игранный', 'PS5 GTA V юзаный', 'PS5 GTA V б\u200b/у',
  'PS5 GTA V Ｂ／Ｕ', 'PS5 GTA V pre-owned', 'PS5 GTA V used',
  'PS5 GTA V Open Box', 'PS5 GTA V refurbished', 'PS5 GTA V resealed',
  'PS5 GTA V отличное состояние', 'PS5 GTA V состояние 5/5',
  'PS5 GTA V Scratch & Dent', 'PS5 GTA V Body Damage', 'PS5 GTA V Repaired',
  'PS5 GTA V без дефектов, но вскрыт', 'PS5 GTA V БУ без царапин',
]) assert.notEqual(reject(name), '', name);
for (const name of [
  'PS5 Новый диск', 'PS5 Бубси', 'PS5 Бумажный мир', 'PS5 Открытый мир',
  'PS5 Новый не вскрыт', 'PS5 Новый невскрытый', 'PS5 Не распечатан',
  'PS5 не использовался', 'PS5 не б/у', 'PS5 ни разу не играл',
  'PS5 без дефектов', 'PS5 без видимых повреждений', 'PS5 без царапин и сколов',
  'PS5 дефектов нет', 'PS5 царапин нет', 'PS5 царапины отсутствуют',
  'PS5 не поврежден', 'PS5 без следов использования', 'PS5 вскрыт не был',
  'PS5 новый, вскрытие при вас', 'PS5 unused', 'PS5 unopened', 'PS5 never used',
  'PS5 no defects', 'PS5 no scratches', 'PS5 not opened',
  'PS5 новый, идеальное состояние',
]) assert.equal(reject(name), '', name);
const excluded = card(undefined, '100 ₽');
const originalQuery = excluded.querySelector;
excluded.querySelector = selector => selector === '[data-marker="item-title"]'
  ? {textContent:'Игра PS5 Б/У',getAttribute:()=>null} : originalQuery(selector);
assert.equal(price(excluded), null, 'Цена б/у не выдаётся даже при прямом вызове распознавания');
console.log('Avito cards: ordinary price has priority, exact kopecks, ambiguous prices never use discount fallback OK');
