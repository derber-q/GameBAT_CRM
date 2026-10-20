(() => {
  const pending = new Set();
  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const requestId = () => crypto.randomUUID?.() || 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
    const value = crypto.getRandomValues(new Uint8Array(1))[0] & 15;
    return (char === 'x' ? value : ((value & 3) | 8)).toString(16);
  });

  async function requestDocument(url, options = {}) {
    const response = await fetch(url, {
      ...options, credentials: 'same-origin', headers: {Accept: 'application/json'},
    });
    if (!response.headers.get('Content-Type')?.includes('application/json')) {
      throw new Error('Не удалось получить стикер. Проверьте вход в CRM и право печати.');
    }
    const document = await response.json();
    if (!response.ok || document.state === 'error' || document.state === 'uncertain') {
      const error = new Error(document.error || document.message || 'Не удалось обработать стикер Яндекса.');
      error.state = document.state;
      error.retryable = response.status === 503;
      throw error;
    }
    return document;
  }

  async function observe(job, display) {
    for (let attempt = 0; attempt < 180; attempt++) {
      display(job.message || 'Подготавливаем и печатаем стикер…');
      if (job.printed) updateControls(job);
      if (job.state === 'done') return job;
      await delay(2000);
      job = await requestDocument(job.status_url);
    }
    throw new Error('Обработка продолжается. Проверьте принтер и статус заказа перед повторной печатью.');
  }

  function updateControls(job) {
    document.querySelectorAll('[data-market-action]').forEach((form) => {
      if (String(form.dataset.marketOrderNumber) !== String(job.order_id)) return;
      const status = form.querySelector('[name="market_status"]');
      const substatus = form.querySelector('[name="market_substatus"]');
      if (status) status.value = job.market_status;
      if (substatus) substatus.value = job.market_substatus;
      if (form.dataset.marketAction === 'ready') {
        form.querySelector('button').disabled = job.market_status !== 'PROCESSING' || job.market_substatus !== 'STARTED';
      }
    });
  }

  window.GameBAT = {...window.GameBAT, marketPrint: {request: requestDocument, requestId, observe}};

  // Делегирование сохраняет печать после AJAX-замены строки продажи.
  document.addEventListener('submit', async (event) => {
    const form = event.target.closest('[data-market-print]');
    if (!form) return;
    event.preventDefault();
    if (pending.has(form.action)) return;
    pending.add(form.action);
    const button = form.querySelector('button');
    const status = form.querySelector('[data-market-print-status]');
    button.disabled = true;
    form.setAttribute('aria-busy', 'true');
    status.textContent = 'Готовим стикер 58×40 мм…';
    const data = new FormData(form);
    form.dataset.printRequestId ||= requestId();
    data.set('request_id', form.dataset.printRequestId);
    try {
      const job = await requestDocument(form.action, {method: 'POST', body: data});
      await observe(job, (text) => {status.textContent = text;});
      delete form.dataset.printRequestId;
    } catch (error) {
      if (error.state === 'error' || error.state === 'uncertain') delete form.dataset.printRequestId;
      status.textContent = error.message || 'Не удалось напечатать стикер. Повторите попытку.';
    } finally {
      pending.delete(form.action);
      button.disabled = false;
      form.removeAttribute('aria-busy');
    }
  });
})();
