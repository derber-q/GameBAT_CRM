(() => {
  'use strict';
  const get = (id) => document.getElementById('consignment-' + id);
  const dialog = get('action-dialog');
  if (!dialog) return;
  const form = get('action-form'), quantity = get('action-quantity');
  const warehouse = get('action-warehouse'), payment = get('action-payment');
  const message = get('action-message');
  let pending = null, busy = false;
  function summary() {
    if (!pending) return;
    get('action-summary').textContent = pending.action === 'return'
      ? `Снять ${quantity.value || '…'} ед. с реализации и вернуть на склад «${warehouse.value ? warehouse.options[warehouse.selectedIndex].textContent : 'выберите склад'}»?`
      : `Подтвердить реализацию ${quantity.value || '…'} ед. товара?`;
  }
  form.addEventListener('input', summary);
  form.addEventListener('change', summary);
  get('action-cancel').addEventListener('click', () => {pending = null; dialog.close();});
  dialog.addEventListener('cancel', () => {pending = null;});
  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-consignment-action]');
    if (!button || busy) return;
    const row = button.closest('[data-consignment-row]');
    const action = button.dataset.consignmentAction;
    pending = {row, action};
    get('action-title').textContent = action === 'return' ? 'Снять с реализации' : 'Товар реализован';
    get('action-product').textContent = `${row.dataset.name} · ${row.dataset.platform}`;
    get('action-available').textContent = `На реализации: ${row.dataset.quantity} шт.`;
    const single = Number(row.dataset.quantity) === 1;
    get('quantity-field').hidden = single;
    quantity.value = single ? '1' : '';
    quantity.max = row.dataset.quantity;
    quantity.readOnly = single;
    warehouse.value = ''; payment.value = '';
    get('return-field').hidden = action !== 'return'; warehouse.disabled = action !== 'return';
    get('payment-field').hidden = action !== 'sold'; payment.disabled = action !== 'sold';
    summary(); dialog.showModal();
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!pending || busy || !form.reportValidity()) return;
    busy = true;
    const {row, action} = pending; pending = null;
    const data = new FormData(form);
    data.set('action', action); data.set('token', row.dataset.token); data.set('confirmed', '1');
    dialog.close();
    row.querySelectorAll('[data-consignment-action]').forEach((button) => {button.disabled = true;});
    message.textContent = `${row.dataset.name}: выполнение…`;
    try {
      const response = await fetch(row.dataset.actionUrl, {method: 'POST', body: data, credentials: 'same-origin', headers: {'Accept': 'application/json'}});
      if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Не удалось подтвердить результат. Обновите список перед повтором.');
      const result = await response.json();
      if (typeof result.row_html === 'string') {
        const group = row.closest('.consignment-product-group');
        const platform = row.closest('.consignment-platform');
        if (result.row_html) row.outerHTML = result.row_html;
        else row.remove();
        const groupCount = group.querySelectorAll('[data-consignment-row]').length;
        group.querySelector('[data-group-count]').textContent = `${groupCount} поз.`;
        group.hidden = groupCount === 0;
        const platformCount = platform.querySelectorAll('[data-consignment-row]').length;
        platform.querySelector('[data-platform-count]').textContent = `${platformCount} поз.`;
        platform.querySelector('[data-platform-empty]').hidden = platformCount > 0;
      }
      message.textContent = `${row.dataset.name}: ${result.message || 'Операция отклонена.'}`;
    } catch (error) {
      message.textContent = `${row.dataset.name}: ${error.message} Остаток не подтверждён — обновите список.`;
    } finally {
      row.querySelectorAll('[data-consignment-action]').forEach((button) => {button.disabled = false;});
      busy = false;
    }
  });
})();
