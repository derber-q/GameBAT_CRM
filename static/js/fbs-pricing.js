(() => {
  'use strict';
  const feeLabels = {
    cost_price: 'Себестоимость', desired_profit: 'Желаемая прибыль', placement_fee: 'Комиссия размещения',
    tax_fee: 'Налог', payment_transfer_fee: 'Перевод денежных средств', delivery_fee: 'Доставка покупателю',
    middle_mile_fee: 'Средняя миля', packaging_fee: 'Упаковка', fixed_payment_fee: 'Фиксированная комиссия',
    other_fbs_fee: 'Другие FBS-расходы', final_price: 'Итоговая цена', actual_profit: 'Фактическая прибыль',
  };
  const money = (value) => {
    const [whole, fraction] = String(value ?? '').split('.');
    return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')}${fraction ? ',' + fraction.padEnd(2, '0') : ''} ₽`;
  };
  const display = (container, result) => {
    const price = container.querySelector('[data-fbs-price]');
    if (price) price.textContent = result.ok ? `Цена для покупателя на Яндекс Маркете: ${money(result.final_price)}` : result.message;
    const profit = container.querySelector('[data-fbs-profit-result]');
    if (profit) profit.textContent = result.ok ? `Расчётная чистая прибыль: ${money(result.actual_profit)}` : '';
    const volume = container.querySelector('[data-fbs-volume]');
    if (volume) volume.textContent = result.ok ? `Габариты для FBS · Вес: ${result.weight_g ?? 'не указан'} г · Расчётный объём: ${result.raw_volume_l} л · Тарифный объём: ${result.billing_volume_l} л` : 'Расчётный и тарифный объём вычисляются из размеров упаковки.';
    const table = container.querySelector('[data-fbs-breakdown]');
    if (table) {
      table.replaceChildren();
      if (result.ok) Object.entries(feeLabels).forEach(([field, label]) => {
        const row = document.createElement('tr');
        [label, money(result[field])].forEach((value) => { const cell = document.createElement('td'); cell.textContent = value; row.appendChild(cell); });
        table.appendChild(row);
      });
    }
  };
  const displayDimensions = (container, complete) => {
    if (!container || typeof complete !== 'boolean') return;
    const button = container.querySelector('[data-fbs-dimensions-open]');
    const fields = container.querySelector('[data-fbs-inputs]');
    const marketPrice = container.closest('td')?.querySelector('[data-price-field="yandex_market_price"]');
    if (button) button.hidden = complete;
    if (fields) fields.hidden = !complete;
    if (marketPrice) marketPrice.hidden = !complete;
  };
  const sourceRows = new WeakMap();
  const request = async (url, data, signal) => {
    const response = await fetch(url, {method: 'POST', body: data, signal, credentials: 'same-origin', headers: {'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json'}});
    if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Проверьте вход в CRM и права доступа.');
    const result = await response.json();
    if (!response.ok && !result.message) throw new Error('Не удалось выполнить расчёт.');
    return result;
  };
  const bindEditor = (root) => {
    root.querySelectorAll('[data-fbs-form]').forEach((form) => {
      if (form.dataset.initialized) return;
      form.dataset.initialized = '1';
      let timer, controller, saving = false;
      const preview = async () => {
        if (saving || !form.isConnected) return;
        controller?.abort(); controller = new AbortController();
        try { display(form, await request(form.dataset.previewUrl, new FormData(form), controller.signal)); }
        catch (error) { if (error.name !== 'AbortError') display(form, {ok: false, message: error.message}); }
      };
      form.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(preview, 250); });
      form.addEventListener('change', () => { clearTimeout(timer); timer = setTimeout(preview, 0); });
      form.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (saving) return;
        const action = event.submitter?.value || 'save';
        if (action === 'apply' && !window.confirm('Применить рассчитанную цену? Для управляемого товара она будет отправлена существующей синхронизацией Яндекс Маркета.')) return;
        const data = new FormData(form); data.set('action', action);
        const sent = Array.from(form.elements).filter((item) => item.name && !item.disabled && item.type !== 'submit').map((item) => [item.name, item.value]);
        saving = true;
        clearTimeout(timer); controller?.abort();
        const status = form.querySelector('[data-fbs-save-status]'); status.textContent = 'Сохранение…';
        try {
          const result = await request(form.action, data);
          if (!result.ok) throw new Error(result.message);
          const changed = sent.some(([name, value]) => form.elements.namedItem(name)?.value !== value);
          form.elements.namedItem('version').value = result.version;
          status.textContent = changed ? 'Сохранено. Есть новые несохранённые изменения.' : result.message;
          if (!changed) display(form, result.calculation);
          const sourceForm = document.getElementById(form.dataset.productPriceForm);
          const sourceRow = sourceRows.get(form) || sourceForm?.closest('[data-price-row]');
          displayDimensions(sourceRow?.querySelector('[data-fbs-inline]'), result.dimensions_complete);
          const sourceProfit = sourceRow?.querySelector('[data-fbs-profit]');
          if (sourceProfit && sourceProfit.value === form.dataset.inlineProfitSnapshot) {
            sourceProfit.value = data.get('yandex_desired_profit') || '';
            form.dataset.inlineProfitSnapshot = sourceProfit.value;
            display(sourceProfit.closest('[data-fbs-inline]'), result.calculation);
          }
          if (result.applied_price !== null) {
            const input = sourceRow?.querySelector('[name="yandex_market_price"]');
            if (input) { input.value = result.applied_price; input.dispatchEvent(new Event('input', {bubbles: true})); }
          }
        } catch (error) { status.textContent = error.message; }
        finally { saving = false; preview(); }
      });
      preview();
      const polling = setInterval(() => {
        if (!form.isConnected) { clearInterval(polling); controller?.abort(); return; }
        if (document.visibilityState === 'visible' && !saving) preview();
      }, 10000);
    });
  };
  document.querySelectorAll('[data-fbs-inline]').forEach((container) => {
    const input = container.querySelector('[data-fbs-profit]');
    const form = input?.form;
    if (!input || !form) return;
    let timer, controller;
    input.addEventListener('input', () => {
      clearTimeout(timer); controller?.abort();
      timer = setTimeout(async () => {
        const data = new FormData(); data.set('inline', '1'); data.set('yandex_desired_profit', input.value);
        data.set('csrfmiddlewaretoken', form.elements.namedItem('csrfmiddlewaretoken').value);
        controller = new AbortController();
        try { display(container, await request(container.dataset.previewUrl, data, controller.signal)); }
        catch (error) { if (error.name !== 'AbortError') display(container, {ok: false, message: error.message}); }
      }, 250);
    });
    form.addEventListener('fbs:saved', (event) => display(container, event.detail));
  });
  const dialog = document.getElementById('fbs-pricing-dialog');
  if (dialog) {
    dialog.querySelector('[data-fbs-close]').addEventListener('click', () => dialog.close());
    let controller;
    document.querySelectorAll('[data-fbs-open]').forEach((link) => link.addEventListener('click', async (event) => {
      event.preventDefault(); controller?.abort(); controller = new AbortController();
      const content = dialog.querySelector('[data-fbs-dialog-content]'); content.textContent = 'Загрузка расчёта…'; dialog.showModal();
      try {
        const response = await fetch(link.href + '?partial=1', {credentials: 'same-origin', signal: controller.signal});
        if (!response.ok || response.redirected) throw new Error('Не удалось открыть расчёт. Проверьте вход в CRM.');
        content.innerHTML = await response.text();
        const editorForm = content.querySelector('[data-fbs-form]');
        const sourceRow = link.closest('[data-price-row]');
        if (editorForm && sourceRow) sourceRows.set(editorForm, sourceRow);
        const sourceProfit = link.closest('[data-fbs-inline]')?.querySelector('[data-fbs-profit]');
        if (editorForm && sourceProfit) {
          editorForm.dataset.inlineProfitSnapshot = sourceProfit.value;
          editorForm.elements.namedItem('yandex_desired_profit').value = sourceProfit.value;
        }
        bindEditor(content);
        if (link.hasAttribute('data-fbs-dimensions-open') && editorForm) {
          const sizes = ['length_cm', 'width_cm', 'height_cm'].map((name) => editorForm.elements.namedItem(name));
          const target = sizes.find((input) => input && !input.disabled && !input.value)
            || sizes.find((input) => input && !input.disabled);
          target?.focus();
        }
      } catch (error) { if (error.name !== 'AbortError') content.textContent = error.message; }
    }));
    dialog.addEventListener('close', () => { controller?.abort(); dialog.querySelector('[data-fbs-dialog-content]').replaceChildren(); });
  }
  bindEditor(document);
})();
