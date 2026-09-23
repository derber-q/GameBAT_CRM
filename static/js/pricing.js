(() => {
  "use strict";

  function decimalToCents(raw) {
    const value = String(raw ?? "").trim().replace(",", ".");
    const match = value.match(/^(\d+)(?:\.(\d{0,2}))?$/);
    if (!match) return null;
    const fraction = (match[2] || "").padEnd(2, "0");
    return BigInt(match[1]) * 100n + BigInt(fraction || "0");
  }

  function money(value) {
    const sign = value < 0n ? "-" : "";
    const absolute = value < 0n ? -value : value;
    return `${sign}${absolute / 100n}.${String(absolute % 100n).padStart(2, "0")}`;
  }
  function read(element) {
    return decimalToCents(element ? (element.tagName === "INPUT" ? element.value : element.dataset.value) : null);
  }
  function updateRow(row) {
    const wholesale = read(row.querySelector('[data-price-field="wholesale_price"]'));
    const cost = decimalToCents(row.dataset.cost);
    row.querySelectorAll('[data-price-field]').forEach((element) => {
      const field = element.dataset.priceField;
      const price = read(element);
      const markup = read(row.querySelector(`[data-markup-for="${field}"]`));
      const reasons = [];
      if (price !== null) {
        if (field !== "wholesale_price" && wholesale !== null && markup !== null && price - wholesale < markup) {
          reasons.push(`Наценка от оптовой цены ниже установленной: ${money(price - wholesale)} ₽ < ${money(markup)} ₽`);
        }
        if (cost !== null && price < cost) reasons.push(`Цена ниже себестоимости: ${money(price)} ₽ < ${money(cost)} ₽`);
      }
      element.classList.toggle("price-warning", reasons.length > 0);
      element.title = reasons.join("\n");
    });
  }

  document.querySelectorAll('[data-price-row]').forEach((row) => {
    updateRow(row);
    row.addEventListener("input", () => updateRow(row));
    row.addEventListener("change", () => updateRow(row));
  });
})();
