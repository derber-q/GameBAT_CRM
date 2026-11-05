/* ReSOURCE: Ручной минимум Avito и передача разрешённого контекста расширению; найденная цена отделена от цены продажи. */
(() => {
  'use strict';
  const extensionStatus = document.querySelector('[data-manual-extension-status]');
  if (extensionStatus) {
    const showExtensionStatus = () => {
      extensionStatus.textContent = document.documentElement.dataset.resourceAvitoConnected === '1'
        ? 'Расширение подключено. Нажмите «Поиск · РФ» или «Поиск · Ростов», чтобы открыть Avito с панелью цены.'
        : 'Панель Avito не подключена. Если расширение уже установлено, обновите эту страницу и заново нажмите кнопку поиска обычной левой кнопкой мыши.';
    };
    showExtensionStatus();
    new MutationObserver(showExtensionStatus).observe(document.documentElement,
      {attributes: true, attributeFilter: ['data-resource-avito-connected']});
  }
  document.querySelectorAll('[data-found-price-form]').forEach(form => {
    const input = form.querySelector('[name="price"]');
    const button = form.querySelector('button');
    const status = form.querySelector('[data-save-status]');
    const date = form.closest('[data-scope-cell]').querySelector('[data-found-date]');
    let pending = false;
    input.addEventListener('input', () => { if (!pending) status.textContent = 'Не сохранено'; });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (pending) return;
      const value = input.value;
      const body = new FormData(form);
      pending = true;
      button.disabled = true;
      status.textContent = 'Сохранение…';
      try {
        const response = await fetch(form.getAttribute('action'), {
          method: 'POST', body, credentials: 'same-origin',
          headers: {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        });
        if (!(response.headers.get('content-type') || '').includes('application/json')) {
          throw new Error('Не удалось сохранить. Проверьте вход и права доступа.');
        }
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.message || 'Ошибка сохранения.');
        if (data.kind !== form.dataset.kind || String(data.product_id) !== form.dataset.productId || data.scope !== form.dataset.scope) {
          throw new Error('Ответ относится к другому товару или географии. Обновите страницу.');
        }
        date.textContent = data.recorded_at;
        form.querySelector('[name="expected_recorded_at"]').value=data.recorded_at_version;
        const warning=form.closest('[data-found-price-row]').querySelector('[data-scope-warning]');
        warning.textContent=data.warning||'';warning.hidden=!data.warning;
        status.textContent = input.value === value ? 'Сохранено' : 'Есть несохранённые изменения';
      } catch (error) {
        status.textContent = error.message || 'Нет соединения. Повторите сохранение.';
      } finally {
        pending = false;
        button.disabled = false;
      }
    });
  });
})();
