(() => {
  'use strict';
  const data = document.getElementById('trip-editor-data');
  if (!data) return;
  const lines = JSON.parse(data.textContent);
  const dialog = document.getElementById('trip-change-dialog');
  const form = document.getElementById('trip-change-form');
  const action = document.getElementById('trip-action');
  const target = document.getElementById('trip-target-supplier');
  const price = document.getElementById('trip-price-supplier');
  const error = document.getElementById('trip-change-error');
  const rows = document.getElementById('trip-customer-rows');
  const save = document.getElementById('trip-change-save');
  let pending = null;
  let busy = false;
  document.querySelectorAll('.trip-return-form').forEach(returnForm => {
    returnForm.addEventListener('submit', async event => {
      event.preventDefault();
      if (busy) return;
      busy = true;
      const button = returnForm.querySelector('button');
      const pageError = document.getElementById('trip-page-error');
      button.disabled = true;
      pageError.textContent = '';
      try {
        const response = await fetch(returnForm.getAttribute('action'), {method: 'POST', body: new FormData(returnForm), credentials: 'same-origin', headers: {'Accept': 'application/json'}});
        if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Не удалось подтвердить возврат. Обновите страницу.');
        const result = await response.json();
        if (!response.ok || !result.success) throw new Error(result.message || 'Не удалось вернуть товар в M.');
        window.location.reload();
      } catch (exception) {
        pageError.textContent = exception.message;
        busy = false;
        button.disabled = false;
      }
    });
  });
  function options(select, entries, label) {
    select.replaceChildren();
    entries.forEach(entry => {
      const option = document.createElement('option');
      option.value = String(entry.id);
      option.textContent = label(entry);
      select.appendChild(option);
    });
  }
  function update() {
    if (!pending) return;
    error.textContent = '';
    const transfer = action.value === 'transfer';
    document.getElementById('trip-transfer-fields').hidden = !transfer;
    document.getElementById('trip-allocation-fields').hidden = transfer;
    target.disabled = !transfer;
    price.disabled = !transfer;
    let total = 0;
    rows.querySelectorAll('input').forEach(input => {
      input.disabled = transfer;
      total += Number(input.value) - Number(input.dataset.elsewhere);
    });
    document.getElementById('trip-allocation-total').textContent = `У этого поставщика распределено: ${total}; должно быть: ${pending.quantity}.`;
  }
  document.querySelectorAll('.trip-line-form').forEach(lineForm => {
    lineForm.addEventListener('submit', event => {
      event.preventDefault();
      if (busy || !lineForm.reportValidity()) return;
      const line = lines[lineForm.dataset.lineId];
      const quantity = Number(lineForm.elements.quantity.value);
      if (quantity === line.quantity) return;
      pending = {line, quantity};
      error.textContent = '';
      document.getElementById('trip-change-product').textContent = line.name;
      document.getElementById('trip-change-amount').textContent = `У поставщика: ${line.quantity} → ${quantity} шт.`;
      const canTransfer = quantity < line.quantity && line.targets.length > 0 && line.prices.length > 0;
      action.value = canTransfer ? 'transfer' : 'adjust';
      document.getElementById('trip-change-mode').hidden = !canTransfer;
      options(target, line.targets, entry => `${entry.name} · приоритет ${entry.priority}`);
      options(price, line.prices, entry => `${entry.name} · ${entry.price} AED`);
      price.value = String(line.price_supplier_id);
      rows.replaceChildren();
      line.allocations.forEach(allocation => {
        const row = document.createElement('tr');
        [`#${allocation.order_id} · ${allocation.recipient}`, allocation.current, allocation.elsewhere].forEach(value => {
          const cell = document.createElement('td');
          cell.textContent = String(value);
          row.appendChild(cell);
        });
        const cell = document.createElement('td');
        const input = document.createElement('input');
        Object.assign(input, {type: 'number', min: String(allocation.elsewhere), max: '2147483647', step: '1', required: true, value: String(allocation.current)});
        input.setAttribute('aria-label', `Получит ${allocation.recipient}`);
        input.dataset.allocationId = String(allocation.allocation_id);
        input.dataset.elsewhere = String(allocation.elsewhere);
        cell.appendChild(input);
        row.appendChild(cell);
        rows.appendChild(row);
      });
      update();
      dialog.showModal();
    });
  });
  action.addEventListener('change', update);
  rows.addEventListener('input', update);
  document.getElementById('trip-change-cancel').addEventListener('click', () => { if (!busy) dialog.close(); });
  dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !pending || !form.reportValidity()) return;
    const distribution = Array.from(rows.querySelectorAll('input')).map(input => ({
      allocation_id: Number(input.dataset.allocationId), final_quantity: input.value,
    }));
    if (action.value === 'adjust') {
      const total = Array.from(rows.querySelectorAll('input')).reduce((sum, input) => sum + Number(input.value) - Number(input.dataset.elsewhere), 0);
      if (total !== pending.quantity) {
        error.textContent = 'Распределите количество между заказчиками: итог должен совпадать с количеством поставщика.';
        return;
      }
    }
    busy = true;
    save.disabled = true;
    error.textContent = '';
    const body = new FormData(form);
    body.set('revision', form.dataset.revision);
    body.set('quantity', String(pending.quantity));
    body.set('distribution', JSON.stringify(distribution));
    try {
      const response = await fetch(pending.line.url, {method: 'POST', body, credentials: 'same-origin', headers: {'Accept': 'application/json'}});
      if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Не удалось подтвердить сохранение. Обновите страницу.');
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.message || 'Не удалось сохранить изменения.');
      window.location.reload();
    } catch (exception) {
      error.textContent = exception.message;
      busy = false;
      save.disabled = false;
    }
  });
})();
