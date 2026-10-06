// Проверка реального скрипта в моделируемом DOM; браузерная приёмка — browser_checks.py.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const code = fs.readFileSync(path.join(__dirname, "../static/resource/storefront.js"), "utf8");
function el(props = {}) {
  return Object.assign({
    events: {}, attrs: {}, style: {setProperty() {}}, dataset: {}, classList: {add() {}, toggle() {}, remove() {}},
    addEventListener(k, f) { (this.events[k] ||= []).push(f); },
    fire(k, e = {}) { (this.events[k] || []).forEach(f => f(e)); },
    setAttribute(k,v) {this.attrs[k]=v;}, removeAttribute(k) {delete this.attrs[k];},
    focus() {this.focused=true;}, querySelector() {return null;}, querySelectorAll() {return [];},
  }, props);
}
const quantity = el({value:"1", min:"1", max:"3", validity:{valid:true},
  stepUp(){this.value=String(+this.value+1);},stepDown(){this.value=String(+this.value-1);}});
const minus=el({dataset:{quantityStep:"-1"}}), plus=el({dataset:{quantityStep:"1"}});
const group=el({querySelector:s=>s==="input"?quantity:s.includes("-1")?minus:plus});
minus.closest=plus.closest=()=>group;
const category=el({name:"category",value:""});
const price=el({name:"price_min",value:""});
const platform=el({name:"platform",value:"2"});
const brand=el({name:"brand",value:"3"});
const groups=[el({dataset:{filterKind:"cd"},querySelectorAll:()=>[platform]}),el({dataset:{filterKind:"tech"},querySelectorAll:()=>[brand]})];
const form=el({elements:[category,price,platform,brand],submitted:0,requestSubmit(){this.submitted++;}});
const sort=el(), search=el({value:""}), headerSearch=el({value:""});
const dialog=el({append(x){this.child=x;},showModal(){this.open=true;},close(){this.open=false;this.fire("close");}});
const slot=el({append(x){this.child=x;}}), panel=el(), open=el(), close=el();
const selectors={"#rs-catalog-form":form,"#id_category":category,"#id_sort":sort,"#id_q":search,"#rs-search":headerSearch,
"#rs-filter-dialog":dialog,"#rs-filters":panel,".rs-filter-slot":slot,".rs-filter-open":open,".rs-filter-close":close};
const root=el({dataset:{contact:"1"},querySelector:s=>selectors[s]||null,
querySelectorAll:s=>s===".rs-quantity"?[group]:s==="[data-filter-kind]"?groups:[]});
const storage=new Map();
const window=el({scrollY:200,innerHeight:844,matchMedia:()=>el(),scrollTo(x,y){this.scrollY=y;}});
const document={body:{style:{}},querySelector:()=>root,addEventListener:(k,f)=>f()};
const context={document,window,location:{pathname:"/opt/catalog/",search:""},sessionStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},requestAnimationFrame:f=>f(),setTimeout,clearTimeout};
vm.runInNewContext(code,context);
assert.equal(minus.disabled,true);
const click = target => root.fire("click",{target:{closest:s=>s==="[data-quantity-step]"?target:null}});
click(plus);click(plus);assert.equal(quantity.value,"3");assert.equal(plus.disabled,true);
click(minus);assert.equal(quantity.value,"2");assert.equal(plus.disabled,false);
open.fire("click");category.value="cd";category.fire("change");price.value="1001";
assert.equal(form.submitted,0);assert.equal(brand.disabled,true);
close.fire("click");assert.equal(price.value,"");assert.equal(category.value,"");
assert.equal(open.focused,true);assert.equal(window.scrollY,200);
sort.fire("change");assert.equal(form.submitted,1);
search.value="Кириллица & +";search.fire("input");assert.equal(headerSearch.value,search.value);
const empty=el();
vm.runInNewContext(code,{...context,document:{...document,querySelector:()=>empty}});
console.log("OK: количество, фильтры без автоприменения, отмена, фокус, поиск, отсутствующие поля");
