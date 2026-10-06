/* Коробки содержат только целые количества; цены в этом интерфейсе не вычисляются. */
(function () {
  'use strict';
  function packBoxes(boxes) {
    return boxes.map(lines => ({items: lines.filter(line => line.count > 0).map(line => {
      if (![line.id, line.count].every(Number.isSafeInteger) || line.count < 1) throw new Error('Количество должно быть положительным целым числом.');
      if (line.total > 0 || line.part > 0) {
        if (line.count !== 1 || !Number.isSafeInteger(line.part) || !Number.isSafeInteger(line.total) || line.part < 1 || line.total < 2 || line.part > line.total) throw new Error('Проверьте номер и общее число частей единицы товара.');
        return {id: line.id, partialCount: {current: line.part, total: line.total}};
      }
      return {id: line.id, fullCount: line.count};
    })}));
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {packBoxes};
  if (typeof document === 'undefined') return;
  document.querySelectorAll('[data-object-list]').forEach(group => {
    const hidden = group.querySelector('input[type=hidden]');
    const rows = group.querySelector('[data-object-rows]');
    function addRow(value = {}) {
      const row = document.createElement('div'); row.className = 'ym-box-line';
      row.append(group.querySelector('template').content.cloneNode(true));
      row.querySelectorAll('[data-object-key]').forEach(input => {input.value = value[input.dataset.objectKey] || ''; input.disabled = hidden.disabled;});
      const remove = row.querySelector('[data-object-remove]'); remove.disabled = hidden.disabled; remove.addEventListener('click', () => row.remove()); rows.append(row);
    }
    let initial = []; try {initial = JSON.parse(hidden.value || '[]');} catch (_) { /* Ошибка отобразится при серверной проверке. */ }
    if (Array.isArray(initial)) initial.forEach(addRow);
    group.querySelector('[data-object-add]')?.addEventListener('click', () => addRow());
    hidden.form?.addEventListener('submit', () => {
      hidden.value = JSON.stringify(Array.from(rows.children).map(row => Object.fromEntries(Array.from(row.querySelectorAll('[data-object-key]')).filter(input => input.value.trim()).map(input => [input.dataset.objectKey, input.value.trim()]))).filter(row => Object.keys(row).length));
    });
  });
  document.querySelectorAll('[data-media-up],[data-media-down]').forEach(button => button.addEventListener('click', () => {
    const row = button.closest('li');
    if (button.hasAttribute('data-media-up') && row.previousElementSibling) row.before(row.previousElementSibling);
    else if (button.hasAttribute('data-media-down') && row.nextElementSibling) row.nextElementSibling.after(row);
  }));
  const form = document.querySelector('[data-box-form]');
  const source = document.getElementById('ym-order-items');
  if (!form || !source) return;
  const items = JSON.parse(source.textContent);
  const container = form.querySelector('[data-boxes]');
  function addBox() {
    const box = document.createElement('div'); box.className = 'ym-box'; box.dataset.box = '';
    const title = document.createElement('h3'); title.textContent = 'Коробка'; box.append(title);
    items.forEach(item => {
      const row = document.createElement('div'); row.className = 'ym-box-line'; row.dataset.item = item.id;
      const text = document.createElement('span'); text.textContent = `${item.offerName || item.offerId} · всего ${item.count}`; row.append(text);
      [['count', 'Количество', 0], ['part', 'Номер части', 0], ['total', 'Всего частей', 0]].forEach(([name, label, value]) => {
        const wrapper = document.createElement('label'); wrapper.textContent = label + ' ';
        const input = document.createElement('input'); input.type = 'number'; input.min = '0'; input.step = '1'; input.value = value; input.dataset[name] = ''; wrapper.append(input); row.append(wrapper);
      }); box.append(row);
    });
    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'button button-secondary'; remove.textContent = 'Убрать коробку'; remove.addEventListener('click', () => box.remove()); box.append(remove); container.append(box);
  }
  form.querySelector('[data-add-box]').addEventListener('click', addBox); addBox();
  form.addEventListener('submit', event => {
    try {
      const boxes = Array.from(container.querySelectorAll('[data-box]')).map(box => Array.from(box.querySelectorAll('[data-item]')).map(row => ({id: Number(row.dataset.item), count: Number(row.querySelector('[data-count]').value), part: Number(row.querySelector('[data-part]').value), total: Number(row.querySelector('[data-total]').value)})));
      const payload = packBoxes(boxes);
      if (!payload.length || payload.some(box => !box.items.length)) throw new Error('В каждой коробке должен быть хотя бы один товар.');
      form.elements.boxes.value = JSON.stringify(payload);
    } catch (error) {event.preventDefault(); const output = form.querySelector('[data-box-error]'); output.hidden = false; output.textContent = error.message;}
  });
})();
