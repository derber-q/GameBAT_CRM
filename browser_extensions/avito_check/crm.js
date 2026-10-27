(() => {
  'use strict';
  if (!ResourceAvito.isCrm(location.href)) return;
  const base = '/crm/pricing/avito-check/';
  const prefix = 'resource-avito:';
  document.documentElement.dataset.resourceAvitoConnected = '1';

  async function request(path, options = {}) {
    let response;
    try {
      response = await fetch(base + path, {credentials: 'same-origin', cache: 'no-store', redirect: 'error',
        signal: AbortSignal.timeout(20000), ...options});
    } catch { throw new Error('CRM недоступна. Проверьте соединение и вход в аккаунт.'); }
    if (!(response.headers.get('content-type') || '').includes('application/json')) {
      throw new Error('Проверьте вход в CRM и права изменения цены.');
    }
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.message || 'CRM не смогла выполнить действие.');
    return data;
  }

  async function bridge(message) {
    if (message.action === 'queue') {
      const params = new URLSearchParams({q: String(message.query || ''), sort: String(message.sort || 'name')});
      const data = await request('manual-context/?' + params);
      return {ok: true, items: data.items};
    }
    if (!Number.isSafeInteger(message.productId) || message.productId <= 0) throw new Error('Некорректный товар.');
    const context = await request('manual-context/?product_id=' + message.productId);
    if (message.action === 'product') return {ok: true, product: context.product};
    if (message.action !== 'save') throw new Error('Неизвестная команда CRM.');
    const body = new URLSearchParams({kind: 'cd', product_id: String(message.productId),
      price: ResourceAvito.price(message.price), manual_queue: '1', expected_recorded_at: String(message.version || '')});
    const saved = await request('found-price/', {method: 'POST', body,
      headers: {'X-CSRFToken': context.csrf_token, 'Accept': 'application/json'}});
    const form = Array.from(document.querySelectorAll('[data-found-price-form]')).find(
      item => item.querySelector('[name="product_id"]')?.value === String(message.productId));
    if (form) {
      form.querySelector('[name="price"]').value = saved.price;
      form.querySelector('[data-save-status]').textContent = 'Сохранено из расширения';
      form.closest('[data-found-price-row]').querySelector('[data-found-date]').textContent = saved.recorded_at;
    }
    return {ok: true};
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.type !== prefix + 'bridge' || sender.id !== chrome.runtime.id || sender.tab) return false;
    bridge(message).then(sendResponse, error => sendResponse({ok: false, message: error.message}));
    return true;
  });

  let starting = false;
  document.addEventListener('click', async event => {
    const link = event.target.closest('[data-avito-manual-product]');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (starting) return;
    starting = true;
    let status = link.parentElement.querySelector('[data-extension-status]');
    if (!status) {
      status = document.createElement('small');
      status.dataset.extensionStatus = '';
      status.setAttribute('role', 'status');
      link.after(status);
    }
    status.textContent = 'Открытие…';
    try {
      const params = new URLSearchParams(location.search);
      const response = await chrome.runtime.sendMessage({type: prefix + 'start',
        productId: Number(link.dataset.avitoManualProduct), query: params.get('q') || '', sort: params.get('sort') || 'name'});
      if (!response?.ok) throw new Error(response?.message || 'Расширение не ответило.');
      status.textContent = '';
    } catch (error) { status.textContent = error.message || 'Обновите вкладку после установки расширения.'; }
    finally { starting = false; }
  });
})();
