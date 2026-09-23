// Run with node pricing/test_pricing_js.cjs. Tests actual browser logic without writes.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const fields = {};
function element(value, dataset, tagName='INPUT') {
  const classes = new Set();
  return {value, dataset, tagName, title:'', classes,
    classList:{toggle(name,on){on?classes.add(name):classes.delete(name);}}};
}
fields.avito_price=element('10150',{priceField:'avito_price'});
fields.wholesale_price=element('10000',{priceField:'wholesale_price'});
fields.yandex_market_price=element('10250',{priceField:'yandex_market_price'});
const markups={avito_price:element('200',{}),yandex_market_price:element('300',{})};
const handlers={};
const row={dataset:{cost:'9000'},
  querySelector(selector){
    const name=selector.match(/="([^"]+)"/)[1];
    return selector.includes('data-price-field')?fields[name]:(markups[name]||null);
  },
  querySelectorAll(){return Object.values(fields);},
  addEventListener(name,fn){handlers[name]=fn;},
};
vm.runInNewContext(fs.readFileSync('static/js/pricing.js','utf8'),{
  document:{querySelectorAll(){return [row];}},
});
const warned=(name)=>fields[name].classes.has('price-warning');
assert(warned('avito_price'));
assert(warned('yandex_market_price'));
assert(!warned('wholesale_price'));
fields.avito_price.value='10200'; handlers.input(); assert(!warned('avito_price'));
fields.avito_price.value='10250'; markups.avito_price.value='300'; handlers.input(); assert(warned('avito_price'));
markups.avito_price.value=''; handlers.input(); assert(!warned('avito_price'));
fields.avito_price.value='8000'; handlers.input(); assert(warned('avito_price')); assert(fields.avito_price.title.includes('себестоимости'));
fields.avito_price.value=''; handlers.input(); assert(!warned('avito_price'));
fields.avito_price.value='10000'; markups.avito_price.value='0'; handlers.input(); assert(!warned('avito_price'));
fields.avito_price.value='9999.99'; handlers.input(); assert(warned('avito_price'));
fields.wholesale_price.value='9900'; handlers.input(); assert(!warned('avito_price')); assert(!warned('yandex_market_price'));
fields.wholesale_price.value='8000'; handlers.input(); assert(warned('wholesale_price'));
// Read-only thresholds and prices retain identical rules.
markups.avito_price=element('',{value:'0.20'},'SPAN');
fields.avito_price.tagName='SPAN'; fields.avito_price.dataset.value='100.20';
fields.wholesale_price.value='100.00'; row.dataset.cost=''; handlers.change(); assert(!warned('avito_price'));
fields.avito_price.dataset.value='100.19'; handlers.input(); assert(warned('avito_price'));
fields.avito_price.dataset.value='999999999999999999.99';
fields.wholesale_price.value='999999999999999999.79'; handlers.input(); assert(!warned('avito_price'));
assert.deepEqual(Object.keys(handlers).sort(),['change','input']); // no submit prevention
console.log('Pricing JS: dynamic price/wholesale/markup, null, zero, readonly, exact cents and large Decimal values OK');
