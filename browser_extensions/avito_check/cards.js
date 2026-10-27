(() => {
  'use strict';
  const cardSelector = '[data-marker="item"]';
  const oldSelector = '[data-marker="old-price-value"], [data-marker="old-price"], [data-marker="price-old"]';
  const currentSelector = '[data-marker="item-price-value"]';

  function amount(text) {
    let value = String(text || '').normalize('NFKC').replace(/\p{Cf}/gu, '').replace(/\s/g, '');
    value = value.replace(/^(?:ценабезскидки|стараяцена|безскидки|цена):?/iu, '');
    const money = value.match(/^(\d+(?:[.,]\d{1,2})?)(?:₽|руб(?:\.|лей|ля)?)(.*)$/iu);
    if (money) {
      const suffix = money[2];
      // В варианте Avito Plus подпись «−3 ₽ бонусами» входит в тот же ценовой узел.
      if (suffix && (!/^(?:[−\-+]|с|бонус|к[еэ]шб[еэ]к|cashback)/iu.test(suffix) ||
          !/(?:бонус|к[еэ]шб[еэ]к|cashback)/iu.test(suffix))) return null;
      value = money[1];
    }
    try { return ResourceAvito.price(value); } catch { return null; }
  }
  function nodeAmount(node) {
    if (!node) return null;
    for (const value of [node.innerText, node.textContent,
      ...['content', 'data-price', 'data-value', 'aria-label'].map(name => node.getAttribute?.(name))]) {
      const result = amount(value);
      if (result) return result;
    }
    return null;
  }
  function oldPriceNode(card) {
    const explicit = card.querySelector(oldSelector) || [...card.querySelectorAll('s, del, strike')].find(node => nodeAmount(node));
    if (explicit) return explicit;
    if (!/(?:бонус|к[еэ]шб[еэ]к|cashback)/iu.test(card.textContent || '')) return null;
    const current = card.querySelector(currentSelector);
    const candidates = [...card.querySelectorAll('span, p, div')].filter(node =>
      (!current || !node.contains(current)) && /(?:бонус|к[еэ]шб[еэ]к|cashback)/iu.test(node.textContent) && nodeAmount(node));
    const amounts = new Set(candidates.map(nodeAmount));
    // У бонусной строки бывает только оформление без data-marker. Разные суммы не угадываем.
    return amounts.size === 1 ? candidates.sort((a, b) => a.textContent.length - b.textContent.length)[0] : null;
  }
  function originalPrice(card) {
    const old = oldPriceNode(card);
    if (old) return nodeAmount(old);
    const current = card.querySelector(currentSelector);
    if (current) return nodeAmount(current);
    const meta = card.querySelector('[data-marker="item-price"] [itemprop="price"][content]');
    return nodeAmount(meta);
  }

  function comparison(price, minimum) {
    function kopecks(value) {
      const [rubles, cents = ''] = ResourceAvito.price(value).split('.');
      return BigInt(rubles) * 100n + BigInt(cents.padEnd(2, '0'));
    }
    try {
      const value = kopecks(price), reference = kopecks(minimum);
      return value < reference ? 'lower' : value > reference ? 'higher' : 'equal';
    } catch { return ''; }
  }
  function formatted(price) {
    const [rubles, cents] = price.split('.');
    return rubles.replace(/\B(?=(\d{3})+(?!\d))/g, '\u00a0') + (cents ? ',' + cents : '') + ' ₽';
  }

  function pricePicker(onPick, onError) {
    let enabled = false;
    let minimum = '';
    let scheduled = false;
    let selected;
    const observer = new MutationObserver(() => {
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => { scheduled = false; paint(); });
    });

    function paint() {
      if (!enabled) return;
      document.querySelectorAll(cardSelector).forEach(card => {
        // Удаление href также закрывает переходы через среднюю кнопку и меню ссылки.
        card.querySelectorAll('a[href]').forEach(link => { link.removeAttribute('href'); });
        card.tabIndex = 0;
        card.setAttribute('role', 'button');
        const price = originalPrice(card);
        card.setAttribute('aria-label', price ? `Выбрать цену без скидки: ${price} рублей` : 'Цена не распознана; введите её вручную');
        card.querySelectorAll('[data-resource-discount-price]').forEach(value => {
          delete value.dataset.resourceDiscountPrice;
          delete value.dataset.resourcePriceText;
        });
        card.querySelectorAll('[data-resource-price-comparison]').forEach(value => { delete value.dataset.resourcePriceComparison; });
        card.querySelectorAll('[data-resource-final-price]').forEach(value => { delete value.dataset.resourceFinalPrice; });
        // Оформление не зависит от распознавания суммы: цена может содержать служебные подписи.
        const old = oldPriceNode(card);
        const final = old || card.querySelector(currentSelector);
        if (final) final.dataset.resourceFinalPrice = '';
        const relation = comparison(price, minimum);
        if (final && relation) final.dataset.resourcePriceComparison = relation;
        if (!old) return;
        old.dataset.resourceOldPrice = '';
        const oldAmount = nodeAmount(old);
        if (oldAmount) {
          old.dataset.resourcePriceText = formatted(oldAmount);
        } else {
          delete old.dataset.resourcePriceText;
        }
        const wrapper = old.closest('[class*="redesignDiscountWrapper-"]') || old.parentElement;
        const current = card.querySelector(currentSelector);
        for (let ancestor = old.parentElement; ancestor && ancestor !== card; ancestor = ancestor.parentElement) {
          if (ancestor.querySelector('[data-marker="item-title"]')) break;
          ancestor.dataset.resourceOldWrapper = '';
          if (current && ancestor.contains(current)) break;
        }
        wrapper.querySelectorAll('[class*="redesignDiscount-"], svg').forEach(line => { line.dataset.resourceOldLine = ''; });
        card.querySelectorAll(currentSelector).forEach(value => {
          if (value === old || value.contains(old)) return;
          value.dataset.resourceDiscountPrice = '';
        });
        // Скрываем весь верхний ценовой блок: Avito может рисовать сумму вне item-price-value.
        card.querySelectorAll('[data-marker="item-price"]').forEach(value => {
          if (!value.contains(old)) value.dataset.resourceDiscountPrice = '';
        });
      });
    }
    function pick(card) {
      const value = originalPrice(card);
      if (!value) { onError('Не удалось однозначно определить цену без скидки. Введите её в панели вручную.'); return; }
      if (onPick(value) === false) return;
      if (selected) delete selected.dataset.resourcePriceSelected;
      selected = card;
      selected.dataset.resourcePriceSelected = '';
    }
    function intercept(event) {
      if (!enabled || !(event.target instanceof Element)) return;
      const card = event.target.closest(cardSelector);
      if (!card) return;
      if (event.type === 'keydown' && !['Enter', ' '].includes(event.key)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (event.type === 'keydown' || ['click', 'auxclick'].includes(event.type) && event.button <= 1) pick(card);
    }
    return {
      setMinimum(value) {
        minimum = value;
        paint();
      },
      start() {
        if (enabled) return;
        enabled = true;
        document.documentElement.dataset.resourceAvitoPicking = '';
        for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click', 'auxclick', 'dblclick', 'contextmenu', 'keydown']) {
          window.addEventListener(type, intercept, {capture: true, passive: false});
        }
        paint();
        observer.observe(document.body || document.documentElement, {subtree: true, childList: true, characterData: true,
          attributes: true, attributeFilter: ['href', 'content', 'data-marker']});
      }
    };
  }
  globalThis.ResourceAvitoCards = Object.freeze({originalPrice, pricePicker, comparison});
})();
