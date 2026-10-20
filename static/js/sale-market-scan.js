(() => {
  const controls = document.getElementById('market-scan-controls');
  const status = document.getElementById('market-scan-status');
  const api = window.GameBAT?.marketPrint;
  if (!controls || !status || !api || !window.GameBAT.registerGlobalBarcodeHandler) return;
  let queue = Promise.resolve();
  const tracked = new Set();
  const failed = new Map();
  const display = (text) => {status.textContent = text;};

  async function scan(barcode, requestId) {
    const data = new FormData(controls);
    data.set('barcode', barcode);
    data.set('request_id', requestId);
    let result;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        result = await api.request(controls.dataset.marketScanUrl, {method: 'POST', body: data});
        break;
      } catch (error) {
        if ((!(error instanceof TypeError) && !error.retryable) || attempt) throw error;
      }
    }
    display(`Заказ №${result.order_id}: отсканировано ${result.scanned} из ${result.required}.`);
    failed.delete(barcode);
    if (result.complete && !tracked.has(result.print_job_id)) {
      tracked.add(result.print_job_id);
      const job = {status_url: result.status_url, message: 'Состав собран. Печатаем стикер…'};
      api.observe(job, (text) => display(`Заказ №${result.order_id}: ${text}`)).catch((error) => display(error.message));
    }
  }

  window.GameBAT.registerGlobalBarcodeHandler((barcode) => {
    if (document.querySelector('dialog[open]')) return;
    queue = queue.catch(() => {}).then(async () => {
      const id = failed.get(barcode) || api.requestId();
      failed.set(barcode, id);
      await scan(barcode, id);
    }).catch((error) => display(error.message));
    return queue;
  });
})();
