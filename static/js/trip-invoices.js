(() => {
  'use strict';
  document.querySelectorAll('[data-trip-invoice-form]').forEach(form => {
    const checkbox = form.querySelector('[name="accepted"]');
    const error = form.querySelector('[data-invoice-error]');
    if (!checkbox || !error) return;
    let busy = false;
    form.addEventListener('submit', event => event.preventDefault());
    checkbox.addEventListener('change', async () => {
      if (busy) return;
      busy = true;
      const accepted = checkbox.checked;
      const body = new FormData(form);
      body.set('accepted', accepted ? '1' : '0');
      checkbox.disabled = true;
      error.textContent = '';
      try {
        const response = await fetch(form.action, {method: 'POST', body, credentials: 'same-origin',
          headers: {'Accept': 'application/json'}});
        if (!(response.headers.get('content-type') || '').includes('application/json')) {
          throw new Error('Не удалось сохранить отметку. Обновите страницу.');
        }
        const result = await response.json();
        if (!response.ok || !result.success) throw new Error(result.message || 'Не удалось сохранить отметку.');
        window.location.hash = form.closest('.trip-supplier-panel').id;
        window.location.reload();
      } catch (exception) {
        checkbox.checked = !accepted;
        checkbox.disabled = false;
        busy = false;
        error.textContent = exception.message;
      }
    });
  });
})();
