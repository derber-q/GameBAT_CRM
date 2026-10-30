(() => {
  'use strict';
  const form = document.querySelector('[data-creditor-debt-form]');
  if (!form) return;
  const total = form.elements.new_debt;
  const amount = form.elements.change_amount;
  const modes = [...form.querySelectorAll('[name="amount_mode"]')];
  const directions = [...form.querySelectorAll('[name="change_direction"]')];
  const preview = form.querySelector('[data-debt-preview]');
  function cents(value) {
    const match = String(value).trim().replace(',', '.').match(/^(-?)(\d+)(?:\.(\d{1,2}))?$/);
    if (!match) return null;
    return (match[1] ? -1n : 1n) * (BigInt(match[2]) * 100n + BigInt((match[3] || '').padEnd(2, '0')));
  }
  const current = cents(JSON.parse(document.getElementById('current-creditor-debt').textContent));
  if (current === null) return;
  const mode = () => modes.find(input => input.checked)?.value || 'total';
  const direction = () => directions.find(input => input.checked)?.value || '+';
  function numeric(value) {
    const absolute = value < 0n ? -value : value;
    return `${value < 0n ? '-' : ''}${absolute / 100n},${String(absolute % 100n).padStart(2, '0')}`;
  }
  function money(value) {
    const [whole, fraction] = numeric(value).split(',');
    return `${value < 0n ? '−' : ''}${new Intl.NumberFormat('ru-RU').format(BigInt(whole.replace('-', '')))},${fraction} ₽`;
  }
  function update() {
    const relative = mode() === 'change';
    form.querySelectorAll('[data-debt-mode-fields]').forEach(group => {
      const active = group.dataset.debtModeFields === mode();
      group.hidden = !active;
      group.querySelectorAll('input').forEach(input => { input.disabled = !active; });
    });
    const value = cents(relative ? amount.value : total.value);
    const valid = value !== null && (!relative || value >= 0n);
    preview.hidden = false;
    preview.textContent = !valid ? 'Введите корректную сумму с точностью до копеек.' : relative
      ? `Итоговая задолженность: ${money(current + (direction() === '-' ? -value : value))}`
      : `Изменение задолженности: ${value - current > 0n ? '+' : ''}${money(value - current)}`;
  }
  modes.forEach(input => input.addEventListener('change', () => {
    if (mode() === 'change') {
      const value = cents(total.value);
      if (value !== null) {
        const delta = value - current;
        directions.forEach(option => { option.checked = option.value === (delta < 0n ? '-' : '+'); });
        amount.value = delta === 0n ? '' : numeric(delta < 0n ? -delta : delta);
      }
    } else {
      const value = cents(amount.value);
      if (value !== null && value >= 0n) total.value = numeric(current + (direction() === '-' ? -value : value));
    }
    update();
  }));
  total.addEventListener('input', update);
  amount.addEventListener('input', update);
  directions.forEach(input => input.addEventListener('change', update));
  update();
})();
