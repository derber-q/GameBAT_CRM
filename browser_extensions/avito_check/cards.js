/* ReSOURCE: Распознавание исходной цены Avito, блокировка перехода по карточке и сравнение с минимумом; неоднозначность не подменяется случайной ценой. */
(() => {
  'use strict';
  const cardSelector = '[data-marker="item"]';
  const oldSelector = '[data-marker="old-price-value"], [data-marker="old-price"], [data-marker="price-old"]';
  const currentSelector = '[data-marker="item-price-value"]';

  // Границы Unicode не дают принять «бумага», «Бубси» или «Unused» за отметку б/у.
  const word = source => new RegExp(`(?<![\\p{L}\\p{N}])(?:${source})(?![\\p{L}\\p{N}])`, 'giu');
  const usedAbbreviation = '(?:[бb6][\\s./\\\\_|-]*[уuy]|б[эе]у|б[эе]?ушн\\p{L}*)';
  const damage = '(?:деф+ект\\p{L}*|брак\\p{L}*|поврежд\\p{L}*|(?:микро)?царап\\p{L}*|поцарап\\p{L}*|скол\\p{L}*|трещин\\p{L}*|тресну\\p{L}*|потертост\\p{L}*|затертост\\p{L}*|коцк\\p{L}*|коцан\\p{L}*)';
  const damageList = `${damage}(?:\\s*(?:,|и)\\s*${damage}){0,8}`;
  const conditionGrade = word('(?:хорош\\p{L}*|отличн\\p{L}*|идеальн\\p{L}*|удовлетворительн\\p{L}*)\\s+состояни\\p{L}*|состояни\\p{L}*\\s*[:=-]?\\s*(?:хорош\\p{L}*|отличн\\p{L}*|идеальн\\p{L}*|удовлетворительн\\p{L}*|5\\s*/\\s*5|10\\s*/\\s*10)');
  const explicitNew = word('новый|новая|новое|новые|запечатан\\p{L}*|невскрыт\\p{L}*|нераспечатан\\p{L}*|brand[ -]?new|factory[ -]?sealed');
  const safePhrases = [
    word(`(?:не\\s*[-]?\\s*|ни\\s+разу\\s+не\\s+)(?:${usedAbbreviation}|вскры\\p{L}*|распечат\\p{L}*|распаков\\p{L}*|использова\\p{L}*|эксплуатирова\\p{L}*|игра\\p{L}*|пользова\\p{L}*|запуска\\p{L}*)`),
    word(`(?:без|нет|нету|не\\s+имеет|не\\s+обнаружено)\\s+(?:(?:видимых|заметных|каких-либо|каких\\s+либо)\\s+)?${damageList}`),
    word(`${damageList}\\s+(?:нет|нету|отсутству\\p{L}*|не\\s+обнаружен\\p{L}*)`),
    word(`не\\s+${damageList}`),
    word('без\\s+следов\\s+(?:использования|эксплуатации|вскрытия)'),
    word('(?:вскрыт\\p{L}*|распечатан\\p{L}*|использован\\p{L}*)\\s+не\\s+был\\p{L}*'),
    word('(?:not|never)\\s+(?:used|opened|played)|no\\s+(?:defects?|scratches|damage)'),
    word('(?:вскрытие|вскрываем|распаковка)\\s+при\\s+(?:вас|покупателе)'),
  ];
  const conditionRules = [
    [word(`${usedAbbreviation}|подержан\\p{L}*|бывш\\p{L}*\\s+(?:в\\s+)?(?:употреблен|использован)\\p{L}*|в\\s+употреблении|с\\s+рук|юзан\\p{L}*|юзал\\p{L}*|поюза\\p{L}*|used|pre[ -]?owned|second[ -]?hand`), 'Б/у или подержанный товар'],
    [word('не\\s+нов\\p{L}*|ненов\\p{L}*|как\\s+нов\\p{L}*|почти\\s+нов\\p{L}*|состояни[ея]\\s+нового'), 'Состояние «как новый» или не новый'],
    [word('вскры\\p{L}*|распечатан\\p{L}*|распакован\\p{L}*|распаковывал\\p{L}*|open[ -]?box|unsealed|не\\s+запечатан\\p{L}*|незапечатан\\p{L}*'), 'Вскрыт или распакован'],
    [word('(?:без|нет)\\s+(?:слюд\\p{L}*|целлофан\\p{L}*|целафан\\p{L}*|обложк\\p{L}*)|(?:снят\\p{L}*|сорван\\p{L}*)\\s+слюд\\p{L}*|(?:надрыв\\p{L}*|разрыв\\p{L}*)\\s+(?:пленк\\p{L}*|упаковк\\p{L}*)'), 'Нет заводской упаковки или она повреждена'],
    [word('(?:без|нет)\\s+(?:(?:заводск\\p{L}*|оригинальн\\p{L}*|защитн\\p{L}*)\\s+)?(?:пленк\\p{L}*|упаковк\\p{L}*|коробк\\p{L}*|пломб\\p{L}*)|(?:открыт\\p{L}*|вскрыт\\p{L}*|порван\\p{L}*|надорван\\p{L}*|помят\\p{L}*|поврежден\\p{L}*|снят\\p{L}*|сорван\\p{L}*)\\s+(?:пленк\\p{L}*|упаковк\\p{L}*|коробк\\p{L}*|пломб\\p{L}*)|(?:пленк\\p{L}*|упаковк\\p{L}*|коробк\\p{L}*|пломб\\p{L}*)\\s+(?:открыт|вскрыт|порван|надорван|помят|поврежден|снят|сорван)\\p{L}*'), 'Нет заводской упаковки или она повреждена'],
    [word(`${damage}|сломан\\p{L}*|поломан\\p{L}*|разбит\\p{L}*|неисправ\\p{L}*|нерабоч\\p{L}*|не\\s+(?:работает|читается|запускается|запустится)|на\\s+запчасти|для\\s+(?:ремонта|запчастей)|defect\\p{L}*|damage(?:d)?|broken|faulty|scratch(?:ed|es)?|dent(?:ed|s)?|repaired`), 'Дефект, повреждение или неисправность'],
    [word('уцен(?:к|ен)\\p{L}*|витринн\\p{L}*|с\\s+витрины|демонстрационн\\p{L}*\\s+образец|восстановл\\p{L}*|после\\s+ремонта|рефаб\\p{L}*|рефурб\\p{L}*|refurb(?:ished)?|reconditioned|renewed|resealed|re-sealed|перезапечатан\\p{L}*|перепакован\\p{L}*|переупакован\\p{L}*'), 'Уценка, витринный или восстановленный товар'],
    [word('использовал\\p{L}*|использован\\p{L}*|эксплуатирова\\p{L}*|пользовал\\p{L}*|играл\\p{L}*|игран\\p{L}*|поиграл\\p{L}*|пройден\\p{L}*|запускал\\p{L}*|следы\\s+(?:использования|эксплуатации)|после\\s+(?:прохождения|использования|распаковки)|один\\s+запуск'), 'Есть признаки использования'],
  ];

  function conditionReason(text) {
    let normalized = String(text || '').slice(0, 8000).normalize('NFKC').toLowerCase()
      .replace(/\p{Cf}/gu, '').replace(/ё/g, 'е').replace(/[‐‑‒–—−]/g, '-').replace(/\s+/g, ' ');
    for (const safe of safePhrases) normalized = normalized.replace(safe, ' ');
    for (const [pattern, reason] of conditionRules) {
      pattern.lastIndex = 0;
      if (pattern.test(normalized)) return reason;
    }
    conditionGrade.lastIndex = explicitNew.lastIndex = 0;
    if (conditionGrade.test(normalized) && !explicitNew.test(normalized)) return 'Описано состояние товара с рук';
    return '';
  }

  function cardCondition(card) {
    // Не читаем весь текст: реклама магазина «скупаем б/у» не описывает состояние лота.
    const title = card.querySelector('[data-marker="item-title"]') || card.querySelector('[itemprop="name"]') || card.querySelector('h3');
    const condition = card.querySelector('[data-marker="item-specific-params"]');
    return conditionReason([title?.textContent, title?.getAttribute?.('title'),
      title?.getAttribute?.('content'), condition?.textContent].filter(Boolean).join(' '));
  }

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
    if (cardCondition(card)) return null;
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

  function pricePicker(onPick, onError, onInvalidated = () => {}) {
    let enabled = false;
    let minimum = '';
    let scheduled = false;
    let selected;
    let selectedValue;
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
        const rejection = cardCondition(card);
        if (rejection) {
          card.dataset.resourceConditionBlocked = rejection;
          card.setAttribute('aria-disabled', 'true');
          card.tabIndex = -1;
          if (selected === card) {
            delete selected.dataset.resourcePriceSelected;
            selected = undefined;
            onInvalidated(selectedValue);
            selectedValue = undefined;
            onError('Выбранное объявление помечено как б/у, вскрытое или с дефектом. Выберите другое объявление.');
          }
        } else {
          delete card.dataset.resourceConditionBlocked;
          card.removeAttribute('aria-disabled');
        }
        const price = originalPrice(card);
        card.setAttribute('aria-label', rejection ? `${rejection}. Исключено из выбора минимальной цены.` :
          price ? `Выбрать цену без скидки: ${price} рублей` : 'Цена не распознана; введите её вручную');
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
        const relation = rejection ? '' : comparison(price, minimum);
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
      const rejection = cardCondition(card);
      if (rejection) {
        onError(`${rejection}. Это объявление нельзя выбрать как минимальную цену.`);
        paint();
        return;
      }
      const value = originalPrice(card);
      if (!value) { onError('Не удалось однозначно определить цену без скидки. Введите её в панели вручную.'); return; }
      if (onPick(value) === false) return;
      if (selected) delete selected.dataset.resourcePriceSelected;
      selected = card;
      selectedValue = value;
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
          attributes: true, attributeFilter: ['href', 'content', 'data-marker', 'title']});
      }
    };
  }
  globalThis.ResourceAvitoCards = Object.freeze({originalPrice, pricePicker, comparison, conditionReason, cardCondition});
})();
