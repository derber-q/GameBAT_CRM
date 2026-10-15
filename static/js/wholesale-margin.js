(() => {
  "use strict";

  const cents = (raw) => {
    const match = String(raw ?? "").trim().replace(",", ".").match(/^(\d+)(?:\.(\d{1,2}))?$/);
    if (!match) return null;
    return BigInt(match[1]) * 100n + BigInt((match[2] || "").padEnd(2, "0"));
  };
  const money = (value) => {
    const absolute = value < 0n ? -value : value;
    return `${value < 0n ? "−" : ""}${absolute / 100n}.${String(absolute % 100n).padStart(2, "0")}`;
  };

  document.querySelectorAll("[data-wholesale-margin]").forEach((pair) => {
    const wholesale = pair.querySelector("[data-wholesale-value]");
    const output = pair.querySelector("[data-wholesale-margin-value]");
    if (!wholesale || !output) return;
    const update = () => {
      const price = cents(wholesale.tagName === "INPUT" ? wholesale.value : wholesale.dataset.value);
      const cost = cents(pair.dataset.cost);
      output.textContent = price === null || cost === null ? "—" : money(price - cost);
    };
    update();
    wholesale.addEventListener("input", update);
    wholesale.addEventListener("change", update);
  });
})();
