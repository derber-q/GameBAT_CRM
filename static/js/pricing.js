(() => {
  "use strict";

  function decimalToCents(raw) {
    const value = String(raw ?? "").trim().replace(",", ".");
    const match = value.match(/^(\d+)(?:\.(\d{0,2}))?$/);
    if (!match) return null;
    const fraction = (match[2] || "").padEnd(2, "0");
    return BigInt(match[1]) * 100n + BigInt(fraction || "0");
  }

  function updateWarning(input) {
    const price = decimalToCents(input.value);
    const cost = decimalToCents(input.dataset.cost);
    const warning = price !== null && cost !== null && price - cost < 20000n;
    input.classList.toggle("avito-low-margin", warning);
    if (warning) {
      input.title = "Наценка относительно себестоимости меньше 200 ₽";
    } else {
      input.removeAttribute("title");
    }
  }

  document.querySelectorAll(".avito-price-input").forEach((input) => {
    updateWarning(input);
    input.addEventListener("input", () => updateWarning(input));
  });
})();
