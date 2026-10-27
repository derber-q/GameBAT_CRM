(() => {
  'use strict';
  const counters = [...document.querySelectorAll('[data-avito-counter]')];
  if (!counters.length) return;
  let busy = false;
  async function refresh() {
    if (busy || document.hidden) return;
    busy = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(counters[0].dataset.countUrl + '?events=1', {
        credentials: 'same-origin', cache: 'no-store', headers: {Accept: 'application/json'}, signal: controller.signal,
      });
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error();
      const counts = await response.json();
      if (![counts.count, counts.publish, counts.unpublish].every(value => Number.isSafeInteger(value) && value >= 0)
          || counts.count !== counts.publish + counts.unpublish) throw new Error();
      counters.forEach(counter => {
        counter.querySelector('[data-avito-action-count]').textContent = counts.count;
        counter.classList.toggle('has-pending', counts.count > 0);
        counter.setAttribute('aria-label', `Avito: необходимых действий — ${counts.count}`);
        counter.title = `Avito: опубликовать — ${counts.publish}, снять — ${counts.unpublish}. По последним данным CRM.`;
      });
      if (window.GameBAT?.avitoRequiredActions) await window.GameBAT.avitoRequiredActions.observe(counts);
      if (window.GameBAT?.avitoAlertSound) await window.GameBAT.avitoAlertSound.observe(counts);
    } catch (_) {
      counters.forEach(counter => {counter.title = 'Avito: показаны последние данные. Не удалось обновить счётчик.';});
    } finally {
      clearTimeout(timeout);
      busy = false;
    }
  }
  window.addEventListener('focus', refresh);
  window.addEventListener('online', refresh);
  document.addEventListener('visibilitychange', refresh);
  setInterval(refresh, 15000);
  void refresh();
})();
