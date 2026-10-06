(() => {
  const form = document.getElementById('avito-check-run');
  if (!form) return;
  const buttons = Array.from(form.querySelectorAll('button[type="submit"]'));
  const status = document.getElementById('avito-check-status');
  const results = document.getElementById('avito-check-results');
  let pending = false;
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (pending) return;
    const body = new FormData(form);
    body.set('action', event.submitter?.value || 'check');
    pending = true;
    buttons.forEach(button => { button.disabled = true; });
    status.textContent = ' Проверяем объявления…';
    try {
      const response = await fetch(form.getAttribute('action'), {
        method: 'POST', body, credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.message || 'Не удалось проверить объявления.');
      results.innerHTML = data.html;
      status.textContent = ' ' + (data.message || 'Проверка завершена.');
    } catch (error) {
      status.textContent = ' ' + (error.message || 'Не удалось связаться с сервером.');
    } finally {
      pending = false;
      buttons.forEach(button => { button.disabled = false; });
    }
  });
})();
