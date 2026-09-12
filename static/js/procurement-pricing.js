document.addEventListener("DOMContentLoaded", () => {
  const money = new Intl.NumberFormat("ru-RU", {minimumFractionDigits: 2, maximumFractionDigits: 2});
  document.querySelectorAll("[data-procurement-row]").forEach((row) => {
    const fields = row.querySelectorAll('input[type="number"]');
    const recalculate = () => {
      const base = Number(row.dataset.base || 0);
      const markup = Number(fields[0]?.value || 0);
      const delivery = Number(fields[1]?.value || 0);
      const prepayment = Math.round((base + markup + delivery) * 100) / 100;
      const surcharge = prepayment < 2000 ? 60 : (prepayment < 3000 ? 80 : 100);
      row.querySelector("[data-prepayment]").textContent = money.format(prepayment);
      row.querySelector("[data-postpayment]").textContent = money.format(prepayment + surcharge);
    };
    fields.forEach((field) => field.addEventListener("input", recalculate));
  });
});
