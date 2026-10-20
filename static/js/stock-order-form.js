(() => {
  "use strict";
  const form = document.querySelector("[data-stock-order-form]");
  if (!form) return;
  const rows = [...form.querySelectorAll("[data-stock-order-row]")];
  const money = (kopecks) => `${(kopecks / 100n).toLocaleString("ru-RU")},${(kopecks % 100n).toString().padStart(2, "0")}`;
  const updateTotals = () => {
    let total = 0n;
    let units = 0n;
    for (const row of rows) {
      const input = row.querySelector("[data-stock-order-quantity]");
      const valid = /^\d+$/.test(input.value) && input.checkValidity();
      const quantity = valid ? BigInt(input.value) : 0n;
      const lineTotal = quantity * BigInt(input.dataset.unitKopecks);
      row.querySelector("[data-stock-order-line-total]").textContent = valid || !input.value ? money(lineTotal) : "—";
      total += lineTotal;
      units += quantity;
    }
    form.querySelector("[data-stock-order-total]").textContent = money(total);
    form.querySelector("[data-stock-order-units]").textContent = units.toLocaleString("ru-RU");
  };
  form.addEventListener("input", (event) => {
    if (event.target.matches("[data-stock-order-quantity]")) updateTotals();
  });
  form.querySelector("[data-stock-order-search]").addEventListener("input", (event) => {
    const query = event.target.value.trim().toLocaleLowerCase("ru-RU");
    let found = false;
    for (const group of form.querySelectorAll("[data-stock-order-group]")) {
      let groupFound = false;
      for (const row of group.querySelectorAll("[data-stock-order-row]")) {
        row.hidden = !row.dataset.search.toLocaleLowerCase("ru-RU").includes(query);
        groupFound ||= !row.hidden;
      }
      group.hidden = !groupFound;
      found ||= groupFound;
    }
    form.querySelector("[data-stock-order-no-results]").hidden = found;
  });
  updateTotals();
})();
