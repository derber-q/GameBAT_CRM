(() => {
  'use strict';
  document.querySelectorAll('[data-found-price-form]').forEach(form => {
    const input = form.querySelector('[name="price"]');
    const button = form.querySelector('button');
    const status = form.querySelector('[data-save-status]');
    const date = form.closest('[data-found-price-row]').querySelector('[data-found-date]');
    let pending = false;
    input.addEventListener('input', () => { if (!pending) status.textContent = 'Не сохранено'; });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (pending) return;
      const value = input.value;
      const body = new FormData(form);
      pending = true;
      button.disabled = true;
      status.textContent = 'Сохранение…';
      try {
        const response = await fetch(form.getAttribute('action'), {
          method: 'POST', body, credentials: 'same-origin',
          headers: {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'},
        });
        if (!(response.headers.get('content-type') || '').includes('application/json')) {
          throw new Error('Не удалось сохранить. Проверьте вход и права доступа.');
        }
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.message || 'Ошибка сохранения.');
        date.textContent = data.recorded_at;
        status.textContent = input.value === value ? 'Сохранено' : 'Есть несохранённые изменения';
      } catch (error) {
        status.textContent = error.message || 'Нет соединения. Повторите сохранение.';
      } finally {
        pending = false;
        button.disabled = false;
      }
    });
  });
})();
