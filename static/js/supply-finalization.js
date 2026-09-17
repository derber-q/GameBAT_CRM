(() => {
  "use strict";

  const form = document.getElementById("supply-finalization-form");
  if (!form) return;

  const rows = Array.from(form.querySelectorAll(".finalization-row"));
  const penaltyBoxes = Array.from(form.querySelectorAll("[data-finalization-penalty]"));
  const applyButton = form.querySelector("[data-apply-finalization]");
  const autoButton = form.querySelector("[data-auto-distribute]");
  const errorBox = form.querySelector("[data-finalization-error]");

  const parseCents = (raw) => {
    const value = String(raw ?? "").trim().replace(",", ".");
    const match = value.match(/^(\d+)(?:\.(\d{1,2}))?$/);
    if (!match) return null;
    return BigInt(match[1]) * 100n + BigInt((match[2] || "").padEnd(2, "0"));
  };

  const formatCents = (value, withSign = true) => {
    const negative = value < 0n;
    const absolute = negative ? -value : value;
    const rubles = (absolute / 100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    const kopecks = (absolute % 100n).toString().padStart(2, "0");
    const sign = negative ? "−" : (withSign && value > 0n ? "+" : "");
    return `${sign}${rubles},${kopecks} ₽`;
  };

  const setSource = (row, source) => {
    const sourceInput = row.querySelector(".finalization-source-input");
    const badge = row.querySelector(".finalization-source");
    const checkbox = row.querySelector('input[name="selected_product"]');
    sourceInput.value = source;
    row.classList.toggle("is-manual", source === "manual");
    row.classList.toggle("is-auto", source === "auto");
    badge.textContent = source === "manual" ? "Вручную" : (source === "auto" ? "Авто" : "");
    if (source === "manual") {
      checkbox.checked = false;
      checkbox.disabled = true;
    } else {
      checkbox.disabled = Number(row.dataset.quantity) === 0;
    }
  };

  const refresh = () => {
    let total = 0n;
    let valid = true;
    let changed = false;
    rows.forEach((row) => {
      const baseline = parseCents(row.dataset.baselineCost);
      const corrected = parseCents(row.querySelector(".finalization-cost-input").value);
      const quantity = BigInt(row.dataset.quantity);
      if (baseline === null || corrected === null) {
        valid = false;
        row.querySelector(".finalization-difference").textContent = "—";
        row.querySelector(".finalization-row-penalty").textContent = "—";
        return;
      }
      const difference = corrected - baseline;
      const rowPenalty = -difference * quantity;
      total += rowPenalty;
      changed = changed || difference !== 0n;
      row.querySelector(".finalization-difference").textContent = formatCents(difference);
      row.querySelector(".finalization-row-penalty").textContent = formatCents(rowPenalty);
    });
    penaltyBoxes.forEach((box) => {
      box.querySelector("strong").textContent = valid ? formatCents(total) : "Некорректное значение";
      box.classList.toggle("finalization-penalty-success", valid && total === 0n);
      box.classList.toggle("finalization-penalty-warning", !valid || total !== 0n);
    });
    applyButton.disabled = !valid || total !== 0n || !changed;
    return {valid, total};
  };

  rows.forEach((row) => {
    const input = row.querySelector(".finalization-cost-input");
    input.addEventListener("input", () => {
      errorBox.textContent = "";
      const baseline = parseCents(row.dataset.baselineCost);
      const corrected = parseCents(input.value);
      setSource(row, corrected !== null && corrected === baseline ? "unchanged" : "manual");
      refresh();
    });
  });

  form.querySelectorAll("[data-select-kind]").forEach((button) => {
    button.addEventListener("click", () => {
      const kind = button.dataset.selectKind;
      rows.forEach((row) => {
        const checkbox = row.querySelector('input[name="selected_product"]');
        if (checkbox.disabled) return;
        checkbox.checked = kind === "all" || kind === row.dataset.productType;
        if (kind === "none") checkbox.checked = false;
      });
    });
  });

  autoButton.addEventListener("click", async () => {
    errorBox.textContent = "";
    const state = refresh();
    if (!state.valid) {
      errorBox.textContent = "Исправьте некорректные значения себестоимости.";
      return;
    }
    autoButton.disabled = true;
    try {
      const response = await fetch(form.dataset.autoUrl, {
        method: "POST",
        body: new FormData(form),
        headers: {"X-Requested-With": "XMLHttpRequest"},
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) throw new Error(payload.error || "Не удалось распределить неустойку.");
      const byKey = new Map(payload.rows.map((row) => [row.key, row]));
      rows.forEach((row) => {
        const result = byKey.get(row.dataset.productKey);
        if (!result) return;
        row.querySelector(".finalization-cost-input").value = result.corrected_cost;
        setSource(row, result.change_source);
      });
      refresh();
    } catch (error) {
      errorBox.textContent = error.message;
    } finally {
      autoButton.disabled = false;
    }
  });

  form.addEventListener("submit", (event) => {
    const state = refresh();
    if (!state.valid || state.total !== 0n || applyButton.disabled) {
      event.preventDefault();
      errorBox.textContent = "Применение возможно только при неустойке 0,00 ₽ и наличии изменений.";
    }
  });

  refresh();
})();
