(() => {
  'use strict';
  const config = document.querySelector('[data-partner-settlement-url]');
  if (!config) return;
  const dialog = document.createElement('dialog');
  dialog.className = 'confirmation-dialog';
  dialog.innerHTML = '<form method="dialog"><h2>Подтвердите расчёт задолженности</h2><div data-summary></div><label>Обязательное примечание<textarea data-note required rows="3"></textarea></label><div class="dialog-actions"><button class="button button-secondary" type="button" data-cancel>Отмена</button><button class="button" type="submit">Подтвердить расчёт</button></div></form>';
  document.body.append(dialog);
  const cents = value => {
    const text = String(value || '').replace(/[^\d,.-]/g, '').replace(',', '.');
    if (!/^\d+(\.\d{1,2})?$/.test(text)) return null;
    const [whole, fraction = ''] = text.split('.');
    return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  };
  const format = value => {
    const [whole, fraction = '00'] = String(value).split('.');
    return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')},${fraction} ₽`;
  };
  const debtLabel = value => value.startsWith('-') ? `GameBAT должен партнёру ${format(value.slice(1))}` : `партнёр должен GameBAT ${format(value)}`;
  async function confirmSettlement({partnerId, saleId, total, received, creationKey, note, csrf, paymentMethod}) {
    if (['cash', 'cash_postpay'].includes(paymentMethod) && cents(received) === 0n) return {token: '', note: null};
    if (!partnerId || received === '' || cents(received) === cents(total)) return {token: '', note: null};
    const data = new FormData();
    Object.entries({partner_id: partnerId, sale_id: saleId || '', total, received,
      creation_key: creationKey || '', csrfmiddlewaretoken: csrf}).forEach(([key, value]) => data.set(key, value));
    const response = await fetch(config.dataset.partnerSettlementUrl, {method: 'POST', body: data, credentials: 'same-origin'});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Не удалось проверить задолженность.');
    if (!result.required) return {token: '', note: null};
    const value = result.values;
    const summary = document.createElement('dl'); summary.className = 'summary';
    for (const [label, text] of [['Стоимость товаров', format(value.total)], ['Получено денег', format(value.received)],
      ['Погашение долга партнёра', format(value.repayment)], ['Взаимозачёт долга GameBAT', format(value.offset)],
      ['Начислено в долг партнёру', format(value.charge || '0.00')],
      ['Обычная переплата', format(value.overpayment)], ['Долг до расчёта', debtLabel(value.debt_before)],
      ['Долг после расчёта', debtLabel(value.debt_after)]]) {
      const title = document.createElement('dt'), amount = document.createElement('dd');
      title.textContent = label; amount.textContent = text; summary.append(title, amount);
    }
    dialog.querySelector('[data-summary]').replaceChildren(summary);
    const input = dialog.querySelector('[data-note]'); input.value = note || '';
    return new Promise(resolve => {
      let confirmed = false;
      dialog.querySelector('form').onsubmit = event => {
        event.preventDefault();
        if (!input.value.trim()) {input.setCustomValidity('Укажите примечание.'); input.reportValidity(); return;}
        confirmed = true; dialog.close();
      };
      dialog.querySelector('[data-cancel]').onclick = () => dialog.close();
      input.oninput = () => input.setCustomValidity('');
      dialog.onclose = () => resolve(confirmed ? {token: result.token, note: input.value.trim()} : null);
      dialog.showModal(); input.focus();
    });
  }
  window.GameBAT = {...window.GameBAT, confirmPartnerSettlement: confirmSettlement};
  document.querySelectorAll('[data-partner-payment-form]').forEach(form => {
    let approved = false, busy = false;
    const paymentPartner = form.querySelector('[data-settlement-partner]');
    if (paymentPartner) {
      const receivedInput = form.querySelector('[name="cash_received_amount"]');
      const updateMinimum = () => { if (receivedInput) receivedInput.min = paymentPartner.value ? '0' : form.dataset.total; };
      paymentPartner.addEventListener('change', updateMinimum);
      updateMinimum();
    }
    form.addEventListener('submit', async event => {
      if (approved) {approved = false; return;}
      if (event.defaultPrevented) return;
      const type = form.querySelector('[name="sale_type"]')?.value;
      const method = form.querySelector('[name="payment_method"]')?.value;
      if (type && (type !== 'wholesale' || !['cash', 'bank_account'].includes(method))) return;
      const choice = paymentPartner?.value || form.querySelector('[name="customer"]')?.value || form.dataset.partnerId;
      if (!choice || choice === 'custom') return;
      const received = form.querySelector('[name="cash_received_amount"]')?.value || '';
      const paymentMethod = method || form.dataset.paymentMethod;
      const total = form.dataset.total || form.querySelector('[data-sale-intermediate-total]')?.textContent.replace(/[^\d,.-]/g, '').replace(',', '.');
      // Без расчёта погашения/взаимозачёта отправляем исходную форму обычным способом.
      if (received === '' || (cents(received) !== null && cents(received) === cents(total))
          || (['cash', 'cash_postpay'].includes(paymentMethod) && cents(received) === 0n)) return;
      event.preventDefault();
      if (busy) return;
      busy = true;
      try {
        const data = new FormData(form), noteInput = form.querySelector('[name="note"]');
        const result = await confirmSettlement({partnerId: choice, saleId: form.dataset.saleId,
          total, received: data.get('cash_received_amount') || '', creationKey: data.get('creation_key'),
          paymentMethod,
          note: noteInput?.value || form.dataset.note || '', csrf: data.get('csrfmiddlewaretoken')});
        if (!result) return;
        function hidden(name, value) {
          let input = form.querySelector(`[name="${name}"]`);
          if (!input) {input = document.createElement('input'); input.type = 'hidden'; input.name = name; form.append(input);}
          input.value = value;
        }
        hidden('settlement_confirmation', result.token);
        if (result.note !== null) {
          if (noteInput) noteInput.value = result.note;
          else hidden('settlement_note', result.note);
        }
        approved = true; form.requestSubmit(event.submitter);
      } catch (error) {window.alert(error.message);}
      finally {busy = false;}
    });
  });
})();
