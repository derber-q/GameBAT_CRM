(() => {
  const section = document.querySelector('#required-actions');
  let previousKeys;
  if (section) {
    window.GameBAT = {...window.GameBAT, avitoRequiredActions: {observe: async snapshot => {
      if (!Array.isArray(snapshot.action_keys)) return;
      const keys = JSON.stringify([...snapshot.action_keys].sort());
      if (keys === previousKeys) return;
      try {
        const response = await fetch(window.location.href, {credentials: 'same-origin', cache: 'no-store'});
        if (!response.ok) return;
        const fresh = new DOMParser().parseFromString(await response.text(), 'text/html');
        const list = fresh.querySelector('[data-required-actions-list]');
        const heading = fresh.querySelector('#required-actions h2');
        if (!list || !heading) return;
        section.querySelector('[data-required-actions-list]').replaceChildren(...list.childNodes);
        section.querySelector('h2').textContent = heading.textContent;
        previousKeys = keys;
      } catch (_) { /* При недоступности остаётся последний полученный список. */ }
    }}};
  }
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
