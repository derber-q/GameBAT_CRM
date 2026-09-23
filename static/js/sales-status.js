(() => {
  'use strict';
  const dialog = document.getElementById('sale-status-dialog');
  if (!dialog) return;
  const form = document.getElementById('sale-status-confirm-form');
  const question = document.getElementById('sale-status-question');
  const cashField = document.getElementById('sale-status-cash-field');
  const cash = document.getElementById('sale-status-cash');
  const message = document.getElementById('sales-status-message');
  let pending = null;
  let busy = false;
  function cancel() { pending = null; dialog.close(); }
  document.getElementById('sale-status-cancel').addEventListener('click', cancel);
  dialog.addEventListener('cancel', () => { pending = null; });
  document.addEventListener('change', (event) => {
    const select = event.target.closest('[data-status-field]');
    if (!select) return;
    const value = select.value;
    const selectedLabel = select.options[select.selectedIndex].textContent;
    select.value = select.dataset.current; // Never display an unconfirmed status.
    if (busy || value === select.dataset.current) return;
    const row = select.closest('[data-sale-row]');
    pending = {row, field: select.dataset.statusField, value};
    question.textContent = `${row.dataset.saleId}: изменить статус ${pending.field === 'order' ? 'заказа' : 'оплаты'} с «${select.options[select.selectedIndex].textContent}» на «${selectedLabel}»?`;
    cashField.hidden = !(pending.field === 'payment' && row.dataset.paymentMethod === 'cash_postpay');
    cash.value = ''; cash.min = row.dataset.total; cash.placeholder = row.dataset.total;
    dialog.showModal();
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!pending || busy) return;
    busy = true;
    const action = pending; pending = null;
    const row = action.row;
    const data = new FormData(form);
    data.set('field', action.field); data.set('value', action.value);
    data.set('version', row.dataset.version); data.set('confirmed', '1');
    dialog.close();
    row.querySelectorAll('[data-status-field]').forEach((control) => { control.disabled = true; });
    message.textContent = `${row.dataset.saleId}: сохранение…`;
    try {
      const response = await fetch(row.dataset.statusUrl, {
        method: 'POST', body: data, credentials: 'same-origin',
        headers: {'Accept': 'application/json'},
      });
      if (!(response.headers.get('content-type') || '').includes('application/json')) {
        throw new Error('Не удалось подтвердить изменение. Проверьте вход в аккаунт и обновите список.');
      }
      const result = await response.json();
      if (result.is_completed || result.is_cancelled) {
        const group = row.closest('[data-sale-group]');
        row.remove();
        const count = group.querySelector('[data-sale-count]');
        count.textContent = Math.max(0, Number(count.textContent) - 1);
        const empty = group.querySelector('[data-sale-empty]');
        empty.hidden = !!group.querySelector('[data-sale-row]');
        if (!empty.hidden && Number(count.textContent) > 0) empty.firstElementChild.textContent = 'На этой странице продаж больше нет. Откройте другую страницу группы.';
      } else if (result.row_html) {
        row.outerHTML = result.row_html;
      }
      message.textContent = `${row.dataset.saleId}: ${result.message || 'Ошибка изменения статуса.'}${result.success && result.is_completed ? ' Продажа перемещена в завершённые.' : ''}`;
    } catch (error) {
      message.textContent = `${row.dataset.saleId}: ${error.message} Обновите список перед повторной попыткой.`;
    } finally {
      row.querySelectorAll('[data-status-field]').forEach((control) => { control.disabled = false; });
      busy = false;
    }
  });
})();
