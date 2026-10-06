const assert = require('node:assert/strict');
const {packBoxes} = require('../static/js/yandex-market.js');
assert.deepEqual(packBoxes([[{id: 7, count: 2, part: 0, total: 0}]]), [{items: [{id: 7, fullCount: 2}]}]);
assert.deepEqual(packBoxes([[{id: 7, count: 1, part: 2, total: 3}]]), [{items: [{id: 7, partialCount: {current: 2, total: 3}}]}]);
assert.throws(() => packBoxes([[{id: 7, count: 1.5, part: 0, total: 0}]]));
assert.throws(() => packBoxes([[{id: 7, count: 2, part: 1, total: 3}]]));
console.log('Yandex Market box tests passed');
