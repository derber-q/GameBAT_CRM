(() => {
  'use strict';
  document.querySelectorAll('[data-formset-add]').forEach((button) => {
    button.addEventListener('click', () => {
      const name = button.dataset.formsetAdd;
      const total = document.querySelector(`[name="${name}-TOTAL_FORMS"]`);
      const container = document.querySelector(`[data-formset="${name}"]`);
      const template = document.querySelector(`[data-formset-template="${name}"]`);
      if (!total || !container || !template) return;
      const content = template.innerHTML.replaceAll('__prefix__', total.value);
      // Шаблон сгенерирован сервером; значения товаров не вставляются в HTML.
      container.insertAdjacentHTML('beforeend', content);
      total.value = String(Number(total.value) + 1);
    });
  });
})();
