(() => {
  "use strict";
  const form = document.getElementById("consignment-transfer-form");
  if (!form) return;
  const lines = document.getElementById("consignment-lines");
  const warehouse = document.getElementById("id_warehouse");
  const barcodeInput = form.querySelector("[data-consignment-barcode-input]");
  const barcodeButton = form.querySelector("[data-consignment-barcode-add]");
  const barcodeFeedback = form.querySelector("[data-consignment-barcode-feedback]");
  const initialLines = JSON.parse(document.getElementById("initial-consignment-lines").textContent);

  function showBarcodeFeedback(message, isError = false) {
    if (!barcodeFeedback) return;
    barcodeFeedback.textContent = message;
    barcodeFeedback.classList.toggle("error-text", isError);
  }

  function removeButton(row) {
    const cell = document.createElement("td");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "remove-row";
    button.title = "Удалить строку";
    button.setAttribute("aria-label", "Удалить строку");
    button.textContent = "×";
    button.addEventListener("click", () => row.remove());
    cell.append(button);
    return cell;
  }

  function addLine(value = {}) {
    const row = document.createElement("tr");
    const productCell = document.createElement("td");
    const wrap = document.createElement("div");
    wrap.className = "autocomplete-wrap";
    const search = document.createElement("input");
    search.type = "text";
    search.name = "product_search";
    search.placeholder = "Начните вводить название товара...";
    search.autocomplete = "off";
    search.required = true;
    search.dataset.productSearch = "true";
    search.value = value.label || "";
    const type = document.createElement("input");
    type.type = "hidden";
    type.name = "product_type";
    type.value = value.product_type || "";
    const id = document.createElement("input");
    id.type = "hidden";
    id.name = "product_id";
    id.value = value.product_id || "";
    const suggestionBox = document.createElement("div");
    suggestionBox.className = "suggestions";
    wrap.append(search, type, id, suggestionBox);
    productCell.append(wrap);

    const quantityCell = document.createElement("td");
    const quantity = document.createElement("input");
    quantity.type = "number";
    quantity.name = "quantity";
    quantity.min = "1";
    quantity.step = "1";
    quantity.required = true;
    quantity.value = value.quantity || "";
    quantityCell.append(quantity);

    const costCell = document.createElement("td");
    costCell.className = "readonly-money";
    costCell.dataset.unitCost = "true";
    const showCost = (result) => {
      costCell.textContent = result && result.cost !== null && result.cost !== ""
        ? `${result.cost} ₽`
        : "—";
    };
    showCost(value);

    const amountCell = document.createElement("td");
    const amount = document.createElement("input");
    amount.type = "number";
    amount.name = "receivable_per_unit";
    amount.min = "0.01";
    amount.step = "0.01";
    amount.required = true;
    amount.placeholder = "0,00";
    amount.value = value.receivable_per_unit || "";
    amountCell.append(amount);

    row.append(productCell, quantityCell, costCell, amountCell, removeButton(row));
    lines.append(row);
    window.GameBAT.attachAutocomplete({
      input: search,
      typeInput: type,
      idInput: id,
      suggestions: suggestionBox,
      endpoint: form.dataset.autocompleteUrl,
      warehouseInput: warehouse,
      searchContext: form.dataset.searchContext,
      onSelect: (result, metadata = {}) => {
        showCost(result);
        if (result && metadata.exactBarcode) {
          if (!quantity.value) quantity.value = "1";
          showBarcodeFeedback(`Добавлено: ${result.label}`);
          amount.focus();
        }
      },
    });
    if (!value.label) search.focus();
    return row;
  }

  function putBarcodeResultIntoTransfer(result) {
    const existingRow = [...lines.querySelectorAll("tr")].find((row) => (
      row.querySelector('input[name="product_type"]')?.value === String(result.type)
      && row.querySelector('input[name="product_id"]')?.value === String(result.id)
    ));
    if (existingRow) {
      const quantity = existingRow.querySelector('input[name="quantity"]');
      if (quantity) quantity.value = String(Math.max(0, Number(quantity.value) || 0) + 1);
      existingRow.querySelector('input[name="receivable_per_unit"]')?.focus();
      return;
    }
    const blankRow = [...lines.querySelectorAll("tr")].find((row) => {
      const id = row.querySelector('input[name="product_id"]');
      const search = row.querySelector('input[name="product_search"]');
      return id && search && !id.value && !search.value.trim();
    });
    if (!blankRow) {
      const row = addLine({
        label: result.label,
        product_type: result.type,
        product_id: result.id,
        quantity: 1,
        cost: result.cost,
      });
      row.querySelector('input[name="receivable_per_unit"]')?.focus();
      return;
    }
    blankRow.querySelector('input[name="product_search"]').value = result.label;
    blankRow.querySelector('input[name="product_type"]').value = result.type;
    blankRow.querySelector('input[name="product_id"]').value = result.id;
    blankRow.querySelector('input[name="quantity"]').value = "1";
    blankRow.querySelector("[data-unit-cost]").textContent = (
      result.cost !== null && result.cost !== "" ? `${result.cost} ₽` : "—"
    );
    blankRow.querySelector('input[name="receivable_per_unit"]')?.focus();
  }

  async function addByBarcode(scannedBarcode = "") {
    const barcode = String(scannedBarcode || barcodeInput?.value || "").trim();
    if (!barcode) {
      showBarcodeFeedback("Введите штрихкод.", true);
      return;
    }
    if (!warehouse?.value) {
      showBarcodeFeedback("Сначала выберите склад.", true);
      return;
    }
    showBarcodeFeedback("Поиск…");
    try {
      const params = new URLSearchParams({
        q: barcode,
        warehouse: warehouse.value,
        context: form.dataset.searchContext || "consignment",
      });
      const response = await fetch(`${form.dataset.autocompleteUrl}?${params.toString()}`, {
        headers: { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest" },
      });
      if (!response.ok) throw new Error("Не удалось выполнить поиск.");
      const payload = await response.json();
      const exactMatches = payload.results.filter(
        (result) => (result.barcodes || [result.barcode]).some(
          (value) => String(value || "").trim() === barcode,
        ),
      );
      if (!exactMatches.length) throw new Error("Товар с таким штрихкодом не найден.");
      if (exactMatches.length > 1) throw new Error("Этот штрихкод указан у нескольких товаров.");
      const result = exactMatches[0];
      if (Number(result.available) <= 0) throw new Error("Этого товара нет на выбранном складе.");
      const existingRow = [...lines.querySelectorAll("tr")].find((row) => (
        row.querySelector('input[name="product_type"]')?.value === String(result.type)
        && row.querySelector('input[name="product_id"]')?.value === String(result.id)
      ));
      const selectedQuantity = Number(existingRow?.querySelector('input[name="quantity"]')?.value) || 0;
      if (selectedQuantity + 1 > Number(result.available)) {
        throw new Error("На выбранном складе недостаточно товара для ещё одной единицы.");
      }
      putBarcodeResultIntoTransfer(result);
      if (barcodeInput) barcodeInput.value = "";
      showBarcodeFeedback(`Добавлено: ${result.label}`);
    } catch (error) {
      showBarcodeFeedback(error.message, true);
    }
  }

  document.getElementById("add-consignment-line").addEventListener("click", () => addLine());
  barcodeButton?.addEventListener("click", () => addByBarcode());
  barcodeInput?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    addByBarcode();
  });
  if (window.GameBAT.registerGlobalBarcodeHandler) {
    window.GameBAT.registerGlobalBarcodeHandler(addByBarcode);
  }
  form.addEventListener("submit", (event) => {
    const productIds = [...lines.querySelectorAll('input[name="product_id"]')];
    if (!productIds.length || !productIds.every((input) => input.value)) {
      event.preventDefault();
      window.alert(productIds.length ? "Выберите существующий товар из списка." : "Добавьте хотя бы один товар.");
    }
  });
  (initialLines.length ? initialLines : [{}]).forEach(addLine);
})();
