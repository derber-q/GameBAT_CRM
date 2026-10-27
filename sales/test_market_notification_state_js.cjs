const assert = require('node:assert/strict');
const {cycleFor, chooseOrder} = require('../static/js/market-notification-state.js');
const start = Date.parse('2026-10-22T12:00:00Z');
const orders = [0, 4, 7].map((minutes, index) => ({id: index + 1, started_at: new Date(start + minutes * 60000).toISOString()}));
const seen = new Map();
assert.equal(cycleFor(orders[0], start - 1), -1);
assert.equal(cycleFor(orders[0], start + 599999), 0);
assert.equal(cycleFor(orders[0], start + 600000), 1);
for (const order of orders) {
  const next = chooseOrder(orders, seen, start + 7 * 60000);
  assert.equal(next.order.id, order.id);
  assert.equal(next.cycle, 0);
  seen.set(String(next.order.id), next.cycle);
}
assert.equal(chooseOrder(orders, seen, start + 9 * 60000), null);
assert.equal(chooseOrder(orders, seen, start + 10 * 60000).order.id, 1);
seen.set('1', 1);
assert.equal(chooseOrder(orders, seen, start + 13 * 60000), null);
assert.equal(chooseOrder(orders, seen, start + 14 * 60000).order.id, 2);
const withoutSecond = orders.filter(row => row.id !== 2);
assert.equal(chooseOrder(withoutSecond, seen, start + 17 * 60000).order.id, 3);
assert.equal(chooseOrder([orders[0]], seen, start + 8 * 3600000).cycle, 48);
console.log('Уведомления: независимые циклы 10 минут, очередь, подтверждение одного заказа и пропущенные часы — OK');
