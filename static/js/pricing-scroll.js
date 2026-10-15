(() => {
  "use strict";
  document.querySelectorAll('.inline-price-form').forEach((form) => {
    const button = form.querySelector('[type="submit"]');
    const status = document.createElement('span');
    status.setAttribute('role', 'status');
    status.style.cssText = 'display:block;min-height:1.4em;width:140px;font-size:11px;line-height:1.4;';
    form.appendChild(status);
    let saving = false;
    let savedValues = null;
    const inputs = Array.from(form.elements).filter((element) => element.matches('[data-price-field]') || element.matches('[data-fbs-profit]'));
    inputs.forEach((input) => input.addEventListener('input', () => {
      if (!saving && savedValues) {
        status.textContent = inputs.some((element, index) => element.value !== savedValues[index])
          ? 'Не сохранено' : 'Сохранено';
      }
    }));
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (saving) return;
      form.dispatchEvent(new CustomEvent('fbs:saving'));
      // FormData включает и поля вне тега form, связанные атрибутом form.
      // Снимок values нужен, чтобы новые правки во время запроса не были
      // ошибочно помечены как уже сохранённые ответом на предыдущие значения.
      const data = new FormData(form);
      const values = inputs.map((element) => element.value);
      saving = true;
      button.disabled = true;
      status.textContent = 'Сохранение…';
      try {
        const response = await fetch(form.action, {
          method: 'POST', body: data, credentials: 'same-origin',
          headers: {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        });
        if (!(response.headers.get('content-type') || '').includes('application/json')) {
          throw new Error('Не удалось сохранить. Проверьте доступ и вход в аккаунт, затем повторите.');
        }
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.message || 'Ошибка сохранения.');
        const profitChanged = inputs.some((element, index) => element.matches('[data-fbs-profit]') && element.value !== values[index]);
        inputs.forEach((element, index) => {
          if (!Object.prototype.hasOwnProperty.call(result.saved_prices || {}, element.name)) return;
          const saved = String(result.saved_prices[element.name] ?? '');
          const unchanged = element.value === values[index];
          if (unchanged && !(element.name === 'yandex_market_price' && profitChanged)) {
            element.value = saved;
            element.dispatchEvent(new CustomEvent('input', {bubbles: true, detail: {fbs: true}}));
          }
          values[index] = saved;
        });
        if (result.calculation && !profitChanged) {
          form.dispatchEvent(new CustomEvent('fbs:saved', {detail: {...result.calculation, update_price: false}}));
        }
        if (Object.prototype.hasOwnProperty.call(result.saved_prices || {}, 'yandex_market_price')) {
          form.dispatchEvent(new CustomEvent('fbs:price-saved', {detail: {price: result.saved_prices.yandex_market_price}}));
        }
        savedValues = values;
        status.textContent = inputs.some((element, index) => element.value !== values[index])
          ? 'Есть новые несохранённые изменения' : 'Сохранено';
      } catch (error) {
        savedValues = null;
        status.textContent = error.message || 'Нет соединения. Повторите сохранение.';
      } finally {
        saving = false;
        button.disabled = false;
      }
    });
  });
})();
