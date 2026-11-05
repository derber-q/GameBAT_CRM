/* ReSOURCE: Связь расширения с ручным поиском CRM и сохранённым минимумом; работает только в разрешённом контексте. */
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
    const identity = ResourceAvito.identity(message);
    const params = new URLSearchParams({product_id: String(identity.productId), kind: identity.kind, scope: identity.scope});
    const context = await request('manual-context/?' + params);
    if (ResourceAvito.key({...context.product, productId: context.product?.id}) !== ResourceAvito.key(identity)) {
      throw new Error('CRM вернула другой товар или географию. Обновите панель.');
    }
    if (message.action === 'product') return {ok: true, product: context.product};
    if (message.action !== 'save') throw new Error('Неизвестная команда CRM.');
    const body = new URLSearchParams({kind: identity.kind, scope: identity.scope, product_id: String(identity.productId),
      price: ResourceAvito.price(message.price), manual_queue: '1', expected_recorded_at: String(message.version || '')});
    const saved = await request('found-price/', {method: 'POST', body,
      headers: {'X-CSRFToken': context.csrf_token, 'Accept': 'application/json'}});
    if (ResourceAvito.key({...saved, productId: saved.product_id}) !== ResourceAvito.key(identity)) {
      throw new Error('Ответ сохранения относится к другому товару или географии. Обновите CRM.');
    }
    const form = Array.from(document.querySelectorAll('[data-found-price-form]')).find(
      item => item.dataset.productId === String(identity.productId) &&
        item.dataset.kind === identity.kind && item.dataset.scope === identity.scope);
    if (form) {
      form.querySelector('[name="price"]').value = saved.price;
      form.querySelector('[data-save-status]').textContent = 'Сохранено из расширения';
      form.querySelector('[name="expected_recorded_at"]').value = saved.recorded_at_version;
      form.closest('[data-scope-cell]').querySelector('[data-found-date]').textContent = saved.recorded_at;
      const warning = form.closest('[data-found-price-row]').querySelector('[data-scope-warning]');
      warning.textContent = saved.warning || '';
      warning.hidden = !saved.warning;
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
        productId: Number(link.dataset.avitoManualProduct), kind: link.dataset.kind, scope: link.dataset.scope,
        query: params.get('q') || '', sort: params.get('sort') || 'name'});
      if (!response?.ok) throw new Error(response?.message || 'Расширение не ответило.');
      status.textContent = '';
    } catch (error) { status.textContent = error.message || 'Обновите вкладку после установки расширения.'; }
    finally { starting = false; }
  });
})();
