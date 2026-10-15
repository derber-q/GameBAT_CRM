(() => {
  "use strict";

  const form = document.querySelector("[data-cost-confirmation-form]");
  const input = form?.querySelector("[data-cost-input]");
  const confirmed = form?.querySelector('[name="cost_confirmed"]');
  if (!form || !input || input.disabled || !confirmed) return;

  const dialog = document.querySelector("[data-cost-confirmation-dialog]");
  const toCents = (raw) => {
    const match = String(raw ?? "").trim().replace(",", ".").match(/^(\d+)(?:\.(\d{0,2}))?$/);
    if (!match) return null;
    return BigInt(match[1]) * 100n + BigInt((match[2] || "").padEnd(2, "0"));
  };
  const money = (cents) => `${cents / 100n}.${String(cents % 100n).padStart(2, "0")}`;
  const oldCost = toCents(form.dataset.cost);
  confirmed.value = "";

  input.addEventListener("input", () => { confirmed.value = ""; });
  form.addEventListener("submit", (event) => {
    const newCost = toCents(input.value);
    if (oldCost === null || newCost === null || oldCost === newCost || confirmed.value === "true") return;
    event.preventDefault();
    if (!dialog || typeof dialog.showModal !== "function") {
      if (window.confirm(`Изменить себестоимость с ${money(oldCost)} ₽ на ${money(newCost)} ₽?`)) {
        confirmed.value = "true";
        form.requestSubmit(event.submitter || undefined);
      }
      return;
    }
    dialog.querySelector("[data-cost-old]").textContent = money(oldCost);
    dialog.querySelector("[data-cost-new]").textContent = money(newCost);
    dialog.showModal();
  });

  if (dialog) {
    dialog.querySelector("[data-cost-cancel]").addEventListener("click", () => dialog.close());
    dialog.querySelector("[data-cost-accept]").addEventListener("click", () => {
      confirmed.value = "true";
      dialog.close();
      form.requestSubmit();
    });
  }
})();
