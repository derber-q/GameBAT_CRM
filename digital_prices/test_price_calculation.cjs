// Только синтетическая арифметика; DOM, сеть и рабочие цены не используются.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {calculate, fractionalSum} = require('../static/js/digital-price-calculation.js');

test('Проценты и коэффициенты складываются точно и не округляются до рублей', () => {
  assert.equal(fractionalSum('6','2','percent'), '+8%');
  assert.equal(fractionalSum('6,01','0.02','percent'), '+6.03%');
  assert.equal(fractionalSum('2.960','0.150','coefficient'), '3.110');
  assert.equal(fractionalSum('2.960','0','coefficient'), '2.960');
  assert.equal(fractionalSum('2.9601','0.0001','coefficient'), '2.9602');
  assert.equal(fractionalSum('0','0','coefficient'), '0.000');
  assert.equal(fractionalSum('2.960','','coefficient'), null);
  assert.equal(fractionalSum('6','-1','percent'), null);
});

test('Предварительная цена повторяет округление сервера и сохраняет копейки', () => {
  for (const [cost, markup, rule, expected] of [
    ['123.45','6','other',130n], ['123,45','6,55','other',130n],
    ['0','0','other',0n], ['50.00','0','other',50n], ['50.01','0','other',60n],
    ['1134','0','ps_plus_subscription',1150n], ['2201','0','xbox_subscription',2250n],
    ['999999999999999999.99','0.01','other',1000000000000000000n]
  ]) assert.equal(calculate(cost, markup, rule, 'RUB'), expected);
});

test('Пустая, отрицательная, неточная и валютная цена не дают ложный предварительный итог', () => {
  for (const invalid of ['', '-1', 'NaN', 'Infinity', '0.001', '1 000', '1e3', '1000000000000000000']) {
    assert.equal(calculate(invalid,'0','other','RUB'), null);
    assert.equal(calculate('100',invalid,'other','RUB'), null);
  }
  assert.equal(calculate('100','0','other','USD'), null);
});
