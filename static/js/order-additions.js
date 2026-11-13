/* ReSOURCE: быстрый выбор новых каталожных товаров для одного закупочного заказа. */
(() => {
  const form = document.querySelector('[data-order-addition-form]');
  const body = form?.querySelector('[data-order-addition-lines]');
  if (!form || !body) return;

  function attach(row) {
    const input = row.querySelector('[data-addition-search]');
    const product = row.querySelector('[name$="-product"]');
    const suggestions = row.querySelector('[data-order-addition-suggestions]');
    if (!input || !product || !suggestions || !window.GameBAT?.attachAutocomplete) return;
    const type = document.createElement('input');
    type.type = 'hidden';
    window.GameBAT.attachAutocomplete({
      input, typeInput: type, idInput: product, suggestions,
      endpoint: form.dataset.searchUrl,
      onSelect: result => { product.value = result ? `${result.type}:${result.id}` : ''; },
    });
  }

  body.querySelectorAll('tr').forEach(attach);
  form.querySelector('[data-order-addition-add]')?.addEventListener('click', () => {
    const total = form.querySelector('[name="lines-TOTAL_FORMS"]');
    if (!total || Number(total.value) >= 100) return;
    const template = form.querySelector('[data-order-addition-template]');
    body.insertAdjacentHTML('beforeend', template.innerHTML.replaceAll('__prefix__', total.value));
    total.value = String(Number(total.value) + 1);
    attach(body.lastElementChild);
    body.lastElementChild.querySelector('[data-addition-search]')?.focus();
  });
})();
