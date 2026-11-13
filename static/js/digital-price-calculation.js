/* Предварительная цена по серверному правилу: целые копейки, без float. */
(() => {
  'use strict';
  function kopecks(value) {
    const text = String(value ?? '').trim().replace(',', '.');
    if (!/^\d+(?:\.\d{0,2})?$/.test(text)) return null;
    const [whole, fraction = ''] = text.split('.');
    if (whole.replace(/^0+/, '').length > 18) return null;
    return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  }
  function calculate(cost, markup, rule, currency) {
    if (currency !== 'RUB') return null;
    const base = kopecks(cost), extra = kopecks(markup);
    if (base === null || extra === null) return null;
    const step = ['ps_plus_subscription', 'xbox_subscription'].includes(rule) ? 5000n : 1000n;
    return ((base + extra + step - 1n) / step) * step / 100n;
  }
  function fractionalSum(cost, markup, mode) {
    const digits = mode === 'coefficient' ? 4 : 2;
    function scaled(raw) {
      const text = String(raw ?? '').trim().replace(',', '.');
      if (!new RegExp('^\\d+(?:\\.\\d{0,' + digits + '})?$').test(text)) return null;
      const [whole, fraction = ''] = text.split('.');
      if (whole.replace(/^0+/, '').length > (digits === 4 ? 16 : 6)) return null;
      return BigInt(whole) * (10n ** BigInt(digits)) + BigInt(fraction.padEnd(digits, '0'));
    }
    const base = scaled(cost), extra = scaled(markup);
    if (base === null || extra === null) return null;
    const total = (base + extra).toString().padStart(digits + 1, '0');
    const whole = total.slice(0, -digits), fraction = total.slice(-digits).replace(/0+$/, '');
    if (mode === 'coefficient') return whole + '.' + fraction.padEnd(3, '0');
    return '+' + whole + (fraction ? '.' + fraction : '') + '%';
  }
  if (typeof module === 'object' && module.exports) module.exports = {calculate, kopecks, fractionalSum};
  else Object.assign(window.GameBAT ||= {}, {calculateDigitalPrice: calculate, sumDigitalTariff: fractionalSum});
})();
