/* ReSOURCE: внутренняя этикетка продажи через прежний агент, без диалога браузера. */
(() => {
  "use strict";
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  const requestId = () => crypto.randomUUID?.() || 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, char => {
    const value = crypto.getRandomValues(new Uint8Array(1))[0] & 15;
    return (char === 'x' ? value : ((value & 3) | 8)).toString(16);
  });
  async function read(url, options = {}) {
    const response = await fetch(url, {...options, credentials: "same-origin", headers: {Accept: "application/json"}});
    if (!response.headers.get("Content-Type")?.includes("application/json")) {
      throw new Error("Проверьте вход в CRM и право просмотра продажи.");
    }
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "Не удалось поставить стикер на печать.");
    return result;
  }
  document.addEventListener("submit", async event => {
    const form = event.target.closest("[data-sale-label-print]");
    if (!form) return;
    event.preventDefault();
    const button = form.querySelector("button");
    if (button.disabled) return;
    const status = form.querySelector("[data-sale-label-status]");
    button.disabled = true;
    form.setAttribute("aria-busy", "true");
    try {
      // Сохраняем ключ при сетевом сбое: повторное нажатие проверяет прежнее задание.
      form.dataset.requestId ||= requestId();
      const body = new FormData(form);
      body.set("request_id", form.dataset.requestId);
      let job = await read(form.action, {method: "POST", body});
      for (let attempt = 0; ; attempt++) {
        status.textContent = job.message;
        if (["done", "error", "uncertain"].includes(job.state)) {
          delete form.dataset.requestId; // Следующая ручная печать — отдельное действие сотрудника.
          break;
        }
        if (attempt >= 180) throw new Error("Задание ещё обрабатывается. Проверьте принтер перед повторным нажатием.");
        await pause(2000);
        job = await read(job.status_url);
      }
    } catch (error) {
      status.textContent = error.message || "Не удалось проверить печать стикера.";
    } finally {
      button.disabled = false;
      form.removeAttribute("aria-busy");
    }
  });
})();
