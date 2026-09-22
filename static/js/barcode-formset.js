document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-barcode-formset]").forEach((container) => {
    const rows = container.querySelector("[data-barcode-rows]");
    const template = container.querySelector("[data-barcode-empty-form]");
    const total = container.querySelector('[name="barcodes-TOTAL_FORMS"]');
    if (!rows || !template || !total) return;

    const bindRemove = (button) => {
      button.addEventListener("click", () => {
        const row = button.closest("[data-barcode-row]");
        const id = row?.querySelector('[name$="-id"]');
        const deletion = row?.querySelector('[name$="-DELETE"]');
        if (!row || !deletion) return;
        if (id?.value) {
          deletion.value = "on";
          row.hidden = true;
        } else {
          row.remove();
        }
      });
    };

    rows.querySelectorAll("[data-barcode-remove]").forEach(bindRemove);
    container.querySelector("[data-barcode-add]")?.addEventListener("click", () => {
      const index = Number(total.value);
      const wrapper = document.createElement("div");
      wrapper.innerHTML = template.innerHTML.replaceAll("__prefix__", String(index)).trim();
      const row = wrapper.firstElementChild;
      if (!row) return;
      rows.appendChild(row);
      total.value = String(index + 1);
      bindRemove(row.querySelector("[data-barcode-remove]"));
      row.querySelector('input[name$="-value"]')?.focus();
    });
  });
});
