(() => {
  const panel = document.querySelector('[data-actions-status-url]');
  if (!panel) return;
  const phase = panel.querySelector('[data-actions-phase]');
  const error = panel.querySelector('[data-actions-error]');
  const started = Date.now();
  const poll = async () => {
    try {
      const response = await fetch(panel.dataset.actionsStatusUrl, {credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      phase.textContent = data.phase;
      error.textContent = [data.error, data.retry_at ? `Повторная попытка: ${data.retry_at}` : ''].filter(Boolean).join(' ');
      error.hidden = !error.textContent;
      if (data.status === 'done' || data.status === 'error') {
        window.location.reload();
        return;
      }
      if (data.status === 'pending' && !data.retry_at && Date.now() - started > 30000) {
        phase.textContent = 'Ожидает обработчика Avito. Возможно, обработчик остановлен или занят другой синхронизацией.';
      }
    } catch (_) {
      phase.textContent = 'Не удалось получить ход обновления. Повторяем запрос…';
    }
    window.setTimeout(poll, 2500);
  };
  poll();
})();
