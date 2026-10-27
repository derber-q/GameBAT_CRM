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
console.log('Avito cards: ordinary price has priority, exact kopecks, ambiguous prices never use discount fallback OK');
