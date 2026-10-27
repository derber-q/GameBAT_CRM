(() => {
  const form = document.querySelector('[data-trip-addition-form]');
  const body = form?.querySelector('[data-addition-lines]');
  if (!body) return;
  let calculationTimer, calculationVersion = 0;
  function calculate() {
    clearTimeout(calculationTimer);
    const version = ++calculationVersion;
    body.querySelectorAll('[data-addition-cost]').forEach(output => { output.setAttribute('aria-busy', 'true'); });
    calculationTimer = setTimeout(async () => {
      try {
        const response = await fetch(form.dataset.calculationUrl, {method: 'POST', body: new FormData(form), headers: {Accept: 'application/json'}});
        const data = await response.json();
        if (version !== calculationVersion) return;
        const updated = new Set();
        for (const result of data.rows || []) {
          const output = body.querySelectorAll('tr')[result.index]?.querySelector('[data-addition-cost]');
          if (output) {
            updated.add(output);
            output.textContent = result.error || `База ${result.base} ₽\nДоставка ${result.delivery} ₽/шт.\nСебестоимость ${result.cost} ₽/шт.\nПрибыль ${result.unit_profit} ₽/шт.\nВсего ${result.expected_profit} ₽`;
          }
        }
        body.querySelectorAll('[data-addition-cost]').forEach(output => {
          output.removeAttribute('aria-busy');
          if (!updated.has(output)) output.textContent = 'Заполните товар, цены и количество для расчёта.';
        });
      } catch (_) {
        if (version === calculationVersion) body.querySelectorAll('[data-addition-cost]').forEach(output => { output.textContent = 'Не удалось обновить расчёт.'; });
      }
    }, 250);
  }
  form.addEventListener('input', calculate);
  form.addEventListener('change', calculate);
  function attach(row) {
    const input = row.querySelector('[data-addition-search]');
    const product = row.querySelector('[name$="-product"]');
    const suggestions = row.querySelector('[data-addition-suggestions]');
    const type = document.createElement('input');
    type.type = 'hidden';
    window.GameBAT.attachAutocomplete({input, typeInput: type, idInput: product, suggestions,
      endpoint: form.dataset.searchUrl,
      onSelect: result => { product.value = result ? `${result.type}:${result.id}` : ''; calculate(); },
    });
  }

  body.querySelectorAll('tr').forEach(attach);
  form.querySelector('[data-addition-add]').addEventListener('click', () => {
    const total = form.querySelector('[name="lines-TOTAL_FORMS"]');
    if (Number(total.value) >= 100) return;
    const template = form.querySelector('[data-addition-template]').innerHTML.replaceAll('__prefix__', total.value);
    body.insertAdjacentHTML('beforeend', template);
    total.value = String(Number(total.value) + 1);
    attach(body.lastElementChild);
    body.lastElementChild.querySelector('[data-addition-search]').focus();
  });
  calculate();
})();
