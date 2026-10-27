(() => {
  'use strict';
  const data = document.getElementById('trip-price-data');
  if (!data) return;
  const lines = JSON.parse(data.textContent);
  const dialog = document.getElementById('trip-price-dialog');
  const form = document.getElementById('trip-price-form');
  const input = document.getElementById('trip-price-input');
  const reason = document.getElementById('trip-price-reason');
  const find = name => form.querySelector(`[data-trip-price-${name}]`);
  const save = find('save'), cancel = find('cancel'), error = find('error');
  const loading = find('loading'), preview = find('preview');
  let selected = null, confirmed = null, busy = false, timer = null, controller = null, sequence = 0;
  function number(value) {
    const parts = String(value).split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    return parts.join(',');
  }
  function show(name, value, warning = false) {
    const node = find(name);
    node.textContent = number(value);
    node.classList.toggle('trip-price-increase', warning);
  }
  const positive = value => !String(value).startsWith('-') && !/^0(?:\.0*)?$/.test(String(value));
  function render(result) {
    show('unit-delta', result.unit_delta_aed, positive(result.unit_delta_aed));
    show('cost-delta', result.cost_delta_rub, positive(result.cost_delta_rub));
    show('profit-delta', result.customer_profit_delta_rub, result.customer_profit_delta_rub.startsWith('-'));
    show('stock-delta', result.stock_cost_delta_rub, positive(result.stock_cost_delta_rub));
    const rows = find('allocations');
    rows.replaceChildren();
    result.allocations.forEach(allocation => {
      const row = document.createElement('tr');
      for (const value of [`#${allocation.order_id} · ${allocation.recipient}${allocation.is_stock ? ' · На склад' : ''}`,
        allocation.quantity, `${number(allocation.rate)} ₽/AED`,
        `${number(allocation.old_unit_cost_rub)} → ${number(allocation.new_unit_cost_rub)}`,
        number(allocation.cost_delta_rub)]) {
        const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
      }
      row.children[2].title = allocation.rate_source;
      rows.append(row);
    });
    const orders = find('orders');
    orders.replaceChildren();
    result.orders.forEach(order => {
      const card = document.createElement('p');
      card.className = 'trip-price-order-summary';
      card.textContent = `Заказ №${order.id}: закупка ${number(order.old_cost_rub)} → ${number(order.new_cost_rub)} ₽.`;
      if (!order.is_stock) {
        const profit = document.createElement('span');
        profit.textContent = ` Прибыль ${number(order.old_profit_rub)} → ${number(order.new_profit_rub)} ₽. Сумма покупателя ${number(order.revenue_rub)} ₽ сохраняется.`;
        profit.classList.toggle('trip-price-loss', order.new_profit_rub.startsWith('-'));
        card.append(profit);
      }
      orders.append(card);
    });
    preview.hidden = false;
  }
  async function post(url, payload, signal) {
    const response = await fetch(url, {method: 'POST', body: payload, credentials: 'same-origin',
      headers: {Accept: 'application/json'}, signal});
    if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Проверьте вход в CRM и обновите страницу.');
    const result = await response.json();
    if (!response.ok || !result.success) throw new Error(result.message || 'Не удалось сохранить закупочную цену.');
    return result;
  }
  function payload() {
    const body = new FormData(form);
    body.set('price_aed', input.value.trim().replace(',', '.'));
    body.set('revision', form.dataset.revision);
    return body;
  }
  async function calculate() {
    if (!selected || busy) return;
    controller?.abort();
    const version = ++sequence;
    const request = new AbortController();
    controller = request;
    const timeout = setTimeout(() => request.abort(), 10000);
    confirmed = null; save.disabled = true; preview.hidden = true; error.textContent = ''; loading.hidden = false;
    try {
      const result = await post(selected.preview_url, payload(), request.signal);
      if (version !== sequence || !dialog.open) return;
      confirmed = result; render(result);
      save.disabled = result.old_price_aed === result.new_price_aed;
    } catch (exception) {
      if (version === sequence && dialog.open) error.textContent = exception.name === 'AbortError'
        ? 'Расчёт не завершился. Измените цену для повторного запроса или обновите страницу.' : exception.message;
    } finally {
      clearTimeout(timeout);
      if (version === sequence) loading.hidden = true;
    }
  }
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-trip-price-edit]');
    if (!button || busy) return;
    selected = lines[button.dataset.tripPriceEdit];
    if (!selected) return;
    input.value = selected.price; reason.value = '';
    find('product').textContent = selected.name;
    find('supplier').textContent = selected.supplier;
    show('old', selected.price); show('quantity', selected.quantity);
    error.textContent = ''; preview.hidden = true; confirmed = null; save.disabled = true;
    dialog.showModal(); input.focus(); input.select();
    void calculate();
  });
  input.addEventListener('input', () => {
    ++sequence; controller?.abort(); clearTimeout(timer);
    confirmed = null; save.disabled = true; preview.hidden = true;
    timer = setTimeout(calculate, 300);
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !confirmed || !selected) return;
    busy = true; save.disabled = true; cancel.disabled = true; input.disabled = true; reason.disabled = true;
    const body = payload();
    body.set('price_aed', confirmed.new_price_aed);
    body.set('reason', reason.value);
    try {
      await post(selected.save_url, body);
      window.location.reload();
    } catch (exception) {
      error.textContent = exception.message;
      busy = false; save.disabled = false; cancel.disabled = false; input.disabled = false; reason.disabled = false;
    }
  });
  cancel.addEventListener('click', () => {if (!busy) dialog.close();});
  dialog.addEventListener('cancel', event => {if (busy) event.preventDefault();});
  dialog.addEventListener('close', () => {
    ++sequence; controller?.abort(); clearTimeout(timer); selected = null; confirmed = null; loading.hidden = true;
  });
})();
