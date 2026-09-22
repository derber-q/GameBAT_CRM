(() => {
  const panel = document.querySelector("[data-avito-sync-status-url]");
  if (!panel) return;

  const setText = (id, value) => {
    const element = document.getElementById(id);
    if (element) element.textContent = String(value ?? "");
  };

  const poll = async () => {
    try {
      const response = await fetch(panel.dataset.avitoSyncStatusUrl, {
        credentials: "same-origin",
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setText("avito-sync-phase", data.phase);
      setText("avito-sync-current", data.current_item);
      for (const [field, id] of Object.entries({
        checked: "avito-sync-checked",
        total: "avito-sync-total",
        changed: "avito-sync-changed",
        stock_changed: "avito-sync-stock-changed",
        price_changed: "avito-sync-price-changed",
        failed: "avito-sync-failed",
        skipped: "avito-sync-skipped",
      })) setText(id, data[field]);
      const bar = document.getElementById("avito-sync-bar");
      if (bar) {
        bar.max = Math.max(Number(data.total) || 0, 1);
        bar.value = Number(data.checked) || 0;
      }
      const error = document.getElementById("avito-sync-error");
      if (error) {
        error.textContent = [
          data.error,
          data.retry_at ? `Следующая попытка: ${data.retry_at}` : "",
        ].filter(Boolean).join(" ");
        error.hidden = !error.textContent;
      }
      const details = document.getElementById("avito-sync-details");
      const list = document.getElementById("avito-sync-error-list");
      if (details && list) {
        list.replaceChildren();
        for (const item of data.details || []) {
          const row = document.createElement("li");
          row.textContent = `№${item.avito_id} · ${item.name} — ${item.error}`;
          list.append(row);
        }
        details.hidden = list.childElementCount === 0;
      }
      if (data.status === "pending" || data.status === "running") {
        window.setTimeout(poll, 2000);
      } else {
        const button = document.querySelector('form[action$="/avito/sync/"] button');
        if (button) button.disabled = false;
      }
    } catch (_) {
      setText("avito-sync-phase", "Не удалось получить ход синхронизации. Повторяем запрос…");
      window.setTimeout(poll, 5000);
    }
  };

  poll();
})();
