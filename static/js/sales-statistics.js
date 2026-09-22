document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("statistics-filter-form");
  if (!form) return;
  const from = form.querySelector('[name="date_from"]');
  const to = form.querySelector('[name="date_to"]');
  const iso = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  form.querySelectorAll("[data-stats-period]").forEach((button) => {
    button.addEventListener("click", () => {
      const today = new Date();
      let start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
      let end = new Date(start);
      switch (button.dataset.statsPeriod) {
        case "yesterday": start.setDate(start.getDate() - 1); end = new Date(start); break;
        case "week": start.setDate(start.getDate() - 6); break;
        case "month": start.setDate(1); break;
        case "previous-month":
          start = new Date(today.getFullYear(), today.getMonth() - 1, 1);
          end = new Date(today.getFullYear(), today.getMonth(), 0);
          break;
        case "year": start = new Date(today.getFullYear(), 0, 1); break;
      }
      from.value = iso(start);
      to.value = iso(end);
    });
  });
  document.querySelectorAll("[data-stats-expand]").forEach((button) => {
    button.addEventListener("click", () => {
      const row = document.getElementById(button.dataset.statsExpand);
      if (!row) return;
      row.hidden = !row.hidden;
      button.setAttribute("aria-expanded", String(!row.hidden));
      button.textContent = row.hidden ? "Состав" : "Свернуть";
    });
  });
});
