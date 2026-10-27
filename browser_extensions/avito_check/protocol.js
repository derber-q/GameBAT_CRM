(() => {
  'use strict';
  const crmHosts = new Set(['127.0.0.1', 'localhost', '192.168.0.131']);
  function isCrm(url) {
    try {
      const value = new URL(url);
      return value.protocol === 'http:' && crmHosts.has(value.hostname) &&
        value.pathname === '/crm/pricing/avito-check/';
    } catch { return false; }
  }
  function isAvito(url) {
    try {
      const value = new URL(url);
      return value.protocol === 'https:' && !value.username && !value.password && !value.port &&
        ['www.avito.ru', 'avito.ru'].includes(value.hostname);
    } catch { return false; }
  }
  function price(value) {
    const text = String(value ?? '').trim().replace(/\s/g, '').replace(',', '.');
    if (!/^\d{1,18}(?:\.\d{1,2})?$/.test(text)) throw new Error('Введите положительную цену с точностью до копеек.');
    const [rubles, cents = ''] = text.split('.');
    if (BigInt(rubles) * 100n + BigInt(cents.padEnd(2, '0')) <= 0n) throw new Error('Цена должна быть больше нуля.');
    return text;
  }
  globalThis.ResourceAvito = Object.freeze({isCrm, isAvito, price});
})();
