/* Сохранение строки с optimistic revision. Деньги не преобразуются в float. */
(() => {
'use strict';

function previewPrice(form) {
  const row = form.closest('tr'), preview = row?.querySelector('[data-price-preview]');
  if (!preview || !window.GameBAT?.calculateDigitalPrice) return;
  const mode = form.elements.namedItem('pricing_mode')?.value || row.dataset.priceMode || 'rub';
  row.querySelectorAll('[data-amount-mode]').forEach(part => {part.hidden = part.dataset.amountMode !== mode;});
  const costField = mode === 'percent' ? 'cost_percent' : mode === 'coefficient' ? 'cost_coefficient' : 'manual_cost';
  const markupField = mode === 'rub' ? 'markup' : 'markup_' + mode;
  const costInput = form.elements.namedItem(costField), markupInput = form.elements.namedItem(markupField);
  const cost = costInput ? costInput.value : mode === 'rub' ? row.dataset.priceCost : row.dataset[mode + 'Cost'];
  let markup = markupInput ? markupInput.value : mode === 'rub' ? row.dataset.priceMarkup : row.dataset[mode + 'Markup'];
  if (row.dataset.priceInherit === '1' && markupInput && markupInput.value.trim() === '') {
    markup = mode === 'rub' ? row.dataset.generalMarkup : row.dataset['general' + (mode === 'percent' ? 'Percent' : 'Coefficient') + 'Markup'];
  }
  const raw = mode === 'rub' ? window.GameBAT.calculateDigitalPrice(cost, markup, row.dataset.priceRule, row.dataset.priceCurrency)
    : window.GameBAT.sumDigitalTariff(cost, markup, mode);
  preview.hidden = false;
  preview.textContent = raw === null ? 'Для расчёта заполните себестоимость и наценку в выбранном режиме.'
    : 'Предварительно: ' + (mode === 'rub' ? raw.toLocaleString('ru-RU') + ' ₽' : raw);
}
document.addEventListener('input', event => {
  const form = event.target.form;
  if (form?.matches('[data-digital-markup]')) {form.dataset.dirty = '1'; previewPrice(form);}
});
document.addEventListener('change', event => {
  const form = event.target.form;
  if (form?.matches('[data-digital-markup]')) {form.dataset.dirty = '1'; previewPrice(form);}
});
document.addEventListener('submit', async event => {
    const form = event.target;
    if (!form.matches('[data-digital-markup]')) return;
    event.preventDefault();
    const button = form.querySelector('button'), status = form.querySelector('[data-save-status]');
    if (button.disabled) return;
    const data = new FormData(form);
    for (const field of ['markup', 'manual_cost', 'cost_percent', 'markup_percent', 'cost_coefficient', 'markup_coefficient']) {
      if (data.has(field)) data.set(field, data.get(field).trim().replace(',', '.'));
    }
    const controls = Array.from(form.elements).filter(control => !control.disabled);
    controls.forEach(control => {control.disabled = true;});
    status.textContent = 'Сохранение…'; status.dataset.error = '0';
    try {
      const response = await fetch(form.action, {method: 'POST', body: data, credentials: 'same-origin'});
      if (response.status === 403) throw new Error('Доступ закрыт. Проверьте текущие разрешения в CRM.');
      if (response.redirected) throw new Error('Войдите в CRM заново и обновите страницу.');
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Ошибка сохранения. Обновите страницу.');
      form.querySelector('[name="revision"]').value = result.revision;
      const row = form.closest('tr');
      row.querySelector('[data-gamebat-price]').textContent = result.price ?? 'Цена уточняется';
      if ('cost' in result) row.dataset.priceCost = result.cost ?? '';
      if ('markup' in result) row.dataset.priceMarkup = result.markup ?? '';
      const profileSource = row.querySelector('[data-buyer-markup-source]');
      if (profileSource) profileSource.textContent = result.inherited_markup ? 'Общая · своя не задана' : 'Индивидуальная';
      if ('pricing_mode' in result) row.dataset.priceMode = result.pricing_mode;
      for (const mode of ['percent', 'coefficient']) {
        if ('cost_' + mode in result) row.dataset[mode + 'Cost'] = result['cost_' + mode] ?? '';
        if ('markup_' + mode in result) row.dataset[mode + 'Markup'] = result['markup_' + mode] ?? '';
      }
      for (const [field, key] of [['markup', 'generalMarkup'], ['markup_percent', 'generalPercentMarkup'],
                                 ['markup_coefficient', 'generalCoefficientMarkup']]) {
        if ('general_' + field in result) row.dataset[key] = result['general_' + field] ?? '';
      }
      const preview = row.querySelector('[data-price-preview]');
      if (preview) preview.hidden = true;
      form.dataset.dirty = '0';
      status.textContent = 'Сохранено';
    } catch (error) {status.textContent = error.message; status.dataset.error = '1';}
    finally {controls.forEach(control => {control.disabled = false;});}
});

document.querySelector('[data-buyer-markup-selector]')?.addEventListener('submit', event => {
  if (document.querySelector('[data-digital-markup][data-dirty="1"]') &&
      !window.confirm('Есть несохранённые наценки. Переключить покупателя без сохранения?')) event.preventDefault();
});

const syncStatus = document.querySelector('[data-digital-sync-status]');
if (syncStatus?.dataset.active === '1') {
  const poll = async () => {
    try {
      const response = await fetch(syncStatus.dataset.digitalSyncStatus, {credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok) throw new Error('Не удалось проверить состояние обновления.');
      const state = await response.json();
      if (state.active) {syncStatus.textContent = 'Каталог обновляется…'; setTimeout(poll, 3000); return;}
      if (state.state === 'done' && String(state.revision) !== syncStatus.dataset.revision) {
        if (!document.querySelector('[data-digital-markup][data-dirty="1"]')) {window.location.reload(); return;}
        syncStatus.textContent = 'Каталог обновлён. Сохраните изменения цен перед обновлением таблицы. ';
        const button = document.createElement('button'); button.type = 'button'; button.className = 'button button-secondary';
        button.textContent = 'Обновить таблицу'; button.onclick = () => window.location.reload(); syncStatus.append(button);
      } else {syncStatus.textContent = state.error || 'Обновление завершено.';}
    } catch (error) {syncStatus.textContent = error.message;}
  };
  setTimeout(poll, 1500);
}
})();
