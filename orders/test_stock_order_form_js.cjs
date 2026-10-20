const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../static/js/stock-order-form.js"), "utf8");

const node = (extra = {}) => ({textContent: "", hidden: false, ...extra});
function row(name, value, cost) {
  const input = node({value, dataset: {unitKopecks: cost},
    matches: selector => selector === "[data-stock-order-quantity]",
    checkValidity() { return /^\d+$/.test(this.value) && BigInt(this.value) <= 2147483647n; }});
  const total = node();
  return node({dataset: {search: name}, input, total,
    querySelector: selector => selector === "[data-stock-order-quantity]" ? input : total});
}
const first = row("Tech · Консоль 000-TECH", "2", "316000");
const second = row("CD · Игра 000-CD", "3", "205025");
const groups = [first, second].map(item => node({querySelectorAll: () => [item]}));
const total = node(), units = node(), empty = node(), search = node();
let searchHandler, inputHandler;
search.addEventListener = (name, callback) => { searchHandler = callback; };
const elements = {"[data-stock-order-total]": total, "[data-stock-order-units]": units,
  "[data-stock-order-no-results]": empty, "[data-stock-order-search]": search};
const form = {querySelector: selector => elements[selector],
  querySelectorAll: selector => selector === "[data-stock-order-row]" ? [first, second] : groups,
  addEventListener: (name, callback) => { inputHandler = callback; }};
vm.runInNewContext(source, {document: {querySelector: () => form}});
const normalized = value => value.replace(/\s/g, " ");
assert.equal(normalized(total.textContent), "12 470,75");
assert.equal(units.textContent, "5");
searchHandler({target: {value: "000-CD"}});
assert.equal(first.hidden, true);
assert.equal(second.hidden, false);
assert.equal(groups[0].hidden, true);
assert.equal(normalized(total.textContent), "12 470,75");
searchHandler({target: {value: "нет такого товара"}});
assert.equal(empty.hidden, false);
searchHandler({target: {value: ""}});
assert.equal(empty.hidden, true);
assert.equal(first.hidden, false);
second.input.value = "-1";
inputHandler({target: second.input});
assert.equal(second.total.textContent, "—");
assert.equal(normalized(total.textContent), "6 320,00");
second.input.value = "1.5";
inputHandler({target: second.input});
assert.equal(second.total.textContent, "—");
second.input.value = "";
inputHandler({target: second.input});
assert.equal(second.total.textContent, "0,00");
first.input.value = "2147483647";
first.input.dataset.unitKopecks = "12345678901234567890";
inputHandler({target: first.input});
assert.equal(total.textContent.replace(/\s/g, ""), "265121435515141626548862948,30");
vm.runInNewContext(source, {document: {querySelector: () => null}});
console.log("stock-order-form: OK");
