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
  const pageError = document.getElementById('trip-page-error');
  let pending = null;
  let busy = false;
  document.querySelectorAll('.trip-return-form').forEach(returnForm => {
    returnForm.addEventListener('submit', async event => {
      event.preventDefault();
      if (busy) return;
      busy = true;
      const button = returnForm.querySelector('button');
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
      option.disabled = !!entry.disabled;
      select.appendChild(option);
    });
  }
  function update() {
    if (!pending) return;
    error.textContent = '';
    const transfer = action.value === 'transfer';
    const automatic = !transfer && automaticReduction();
    document.getElementById('trip-transfer-fields').hidden = !transfer;
    document.getElementById('trip-allocation-fields').hidden = transfer || automatic;
    const automaticHint = document.getElementById('trip-automatic-adjustment');
    automaticHint.hidden = !automatic;
    automaticHint.textContent = pending.quantity === 0
      ? 'Доли этого поставщика во всех связанных заказах станут нулевыми. Количества у других поставщиков сохранятся.'
      : 'Количество связанного заказа изменится автоматически. Количества у других поставщиков сохранятся.';
    target.disabled = !transfer;
    price.disabled = !transfer;
    let total = 0;
    rows.querySelectorAll('input').forEach(input => {
      input.disabled = transfer || automatic;
      total += Number(input.value) - Number(input.dataset.elsewhere);
    });
    document.getElementById('trip-allocation-total').textContent = `У этого поставщика распределено: ${total}; должно быть: ${pending.quantity}.`;
  }
  function automaticReduction() {
    return pending.quantity < pending.line.quantity && (pending.quantity === 0 ||
      pending.line.allocations.filter(allocation => allocation.current > allocation.elsewhere).length === 1);
  }

  async function saveChange(distribution, inline = false) {
    if (busy || !pending) return;
    busy = true;
    save.disabled = true;
    error.textContent = '';
    pageError.textContent = '';
    const change = pending;
    const controls = inline ? Array.from(change.sourceForm.querySelectorAll('input, button')) : [];
    controls.forEach(control => { control.disabled = true; });
    const body = new FormData(form);
    body.set('action', action.value);
    body.set('revision', form.dataset.revision);
    body.set('quantity', String(change.quantity));
    body.set('distribution', JSON.stringify(distribution));
    try {
      const response = await fetch(change.line.url, {method: 'POST', body, credentials: 'same-origin', headers: {'Accept': 'application/json'}});
      if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Не удалось подтвердить сохранение. Обновите страницу.');
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.message || 'Не удалось сохранить изменения.');
      window.location.reload();
    } catch (exception) {
      (inline ? pageError : error).textContent = exception.message;
      busy = false;
      save.disabled = false;
      controls.forEach(control => { control.disabled = false; });
    }
  }
  document.querySelectorAll('.trip-line-form').forEach(lineForm => {
    lineForm.addEventListener('submit', event => {
      event.preventDefault();
      if (busy || !lineForm.reportValidity()) return;
      const line = lines[lineForm.dataset.lineId];
      const quantity = Number(lineForm.elements.quantity.value);
      if (quantity === line.quantity) return;
      pending = {line, quantity, sourceForm: lineForm};
      error.textContent = '';
      document.getElementById('trip-change-product').textContent = line.name;
      document.getElementById('trip-change-amount').textContent = `У поставщика: ${line.quantity} → ${quantity} шт.`;
      const canTransfer = !line.is_last_supplier && quantity < line.quantity && line.targets.length > 0 && line.prices.length > 0;
      action.value = canTransfer ? 'transfer' : 'adjust';
      document.getElementById('trip-change-mode').hidden = !canTransfer;
      document.getElementById('trip-priority-ambiguity').hidden = !line.priority_ambiguous || !canTransfer;
      options(target, line.targets, entry => `${entry.name} · приоритет ${entry.priority}${entry.disabled ? ' · инвойс принят' : ''}`);
      options(price, line.prices, entry => `${entry.name} · ${entry.price} AED`);
      price.value = String(line.price_supplier_id);
      rows.replaceChildren();
      if (!canTransfer && automaticReduction()) {
        saveChange(null, true);
        return;
      }
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
  document.getElementById('trip-change-cancel').addEventListener('click', () => { if (!busy) { pending = null; dialog.close(); } });
  dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); else pending = null; });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !pending || !form.reportValidity()) return;
    const manual = action.value === 'adjust' && !automaticReduction();
    const distribution = manual ? Array.from(rows.querySelectorAll('input')).map(input => ({
      allocation_id: Number(input.dataset.allocationId), final_quantity: input.value,
    })) : null;
    if (manual) {
      const total = Array.from(rows.querySelectorAll('input')).reduce((sum, input) => sum + Number(input.value) - Number(input.dataset.elsewhere), 0);
      if (total !== pending.quantity) {
        error.textContent = 'Распределите количество между заказчиками: итог должен совпадать с количеством поставщика.';
        return;
      }
    }
    await saveChange(distribution);
  });
})();
