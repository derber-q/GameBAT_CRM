(() => {
  "use strict";
  document.querySelectorAll(".stock-lines-form").forEach((form) => {
    const body = form.querySelector(".stock-lines");
    const add = form.querySelector(".add-stock-line");
    const initialNode = form.dataset.initialItemsId ? document.getElementById(form.dataset.initialItemsId) : null;
    const initial = initialNode ? JSON.parse(initialNode.textContent) : [];
    const warehouseInput = form.dataset.warehouseSelectId ? document.getElementById(form.dataset.warehouseSelectId) : null;
    const barcodeInput = form.querySelector("[data-sale-barcode-input]");
    const barcodeButton = form.querySelector("[data-sale-barcode-add]");
    const barcodeFeedback = form.querySelector("[data-sale-barcode-feedback]");

    function addLine(value = {}) {
      const row = document.createElement("tr");
      const productCell = document.createElement("td");
      const wrap = document.createElement("div");
      wrap.className = "autocomplete-wrap";
      const search = document.createElement("input");
      search.type = "text";
      search.dataset.productSearch = "true";
      search.placeholder = "Название, артикул или штрихкод";
      search.autocomplete = "off";
      search.required = true;
      search.value = value.label || "";
      const type = document.createElement("input");
      type.type = "hidden";
      type.name = "product_type";
      type.value = value.product_type || "";
      const id = document.createElement("input");
      id.type = "hidden";
      id.name = "product_id";
      id.value = value.product_id || "";
      const suggestions = document.createElement("div");
      suggestions.className = "suggestions";
      wrap.append(search, type, id, suggestions);
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

      const removeCell = document.createElement("td");
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "remove-row";
      remove.setAttribute("aria-label", "Удалить строку");
      remove.textContent = "×";
      remove.addEventListener("click", () => row.remove());
      removeCell.append(remove);
      row.append(productCell, quantityCell, removeCell);
      body.append(row);
      window.GameBAT.attachAutocomplete({
        input: search,
        typeInput: type,
        idInput: id,
        suggestions,
        endpoint: form.dataset.autocompleteUrl,
        warehouseId: form.dataset.warehouseId,
        warehouseInput,
      });
      if (!value.label) search.focus();
    }

    function putBarcodeResultIntoSale(result) {
      const blankRow = [...body.querySelectorAll("tr")].find((row) => {
        const productId = row.querySelector('input[name="product_id"]');
        const productSearch = row.querySelector("[data-product-search]");
        return productId && productSearch && !productId.value && !productSearch.value.trim();
      });
      if (blankRow) {
        blankRow.querySelector("[data-product-search]").value = result.label;
        blankRow.querySelector('input[name="product_type"]').value = result.type;
        blankRow.querySelector('input[name="product_id"]').value = result.id;
        const quantity = blankRow.querySelector('input[name="quantity"]');
        if (quantity && !quantity.value) quantity.value = "1";
        if (quantity) quantity.focus();
        return;
      }
      addLine({
        label: result.label,
        product_type: result.type,
        product_id: result.id,
        quantity: 1,
      });
    }

    async function addByBarcode() {
      if (!barcodeInput || !barcodeFeedback) return;
      const barcode = barcodeInput.value.trim();
      barcodeFeedback.classList.remove("error-text");
      if (barcode.length < 2) {
        barcodeFeedback.textContent = "Введите штрихкод.";
        barcodeFeedback.classList.add("error-text");
        return;
      }
      const selectedWarehouse = warehouseInput ? warehouseInput.value : form.dataset.warehouseId;
      if (!selectedWarehouse) {
        barcodeFeedback.textContent = "Сначала выберите склад.";
        barcodeFeedback.classList.add("error-text");
        return;
      }
      barcodeFeedback.textContent = "Поиск…";
      try {
        const response = await fetch(
          `${form.dataset.autocompleteUrl}?q=${encodeURIComponent(barcode)}&warehouse=${encodeURIComponent(selectedWarehouse)}`,
          { headers: { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest" } },
        );
        if (!response.ok) throw new Error("Не удалось выполнить поиск.");
        const payload = await response.json();
        const exactMatches = payload.results.filter(
          (result) => String(result.barcode || "").trim() === barcode,
        );
        if (exactMatches.length === 0) {
          throw new Error("Товар с таким штрихкодом не найден.");
        }
        if (exactMatches.length > 1) {
          throw new Error("Этот штрихкод указан у нескольких товаров. Выберите товар через обычный поиск.");
        }
        const result = exactMatches[0];
        if (Number(result.available) <= 0) {
          throw new Error("Этого товара нет на выбранном складе.");
        }
        putBarcodeResultIntoSale(result);
        barcodeInput.value = "";
        barcodeFeedback.textContent = `Добавлено: ${result.label}`;
        barcodeInput.focus();
      } catch (error) {
        barcodeFeedback.textContent = error.message;
        barcodeFeedback.classList.add("error-text");
      }
    }

    add.addEventListener("click", () => addLine());
    if (barcodeButton) barcodeButton.addEventListener("click", addByBarcode);
    if (barcodeInput) {
      barcodeInput.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        addByBarcode();
      });
    }
    form.addEventListener("submit", (event) => {
      const selected = [...body.querySelectorAll('input[name="product_id"]')].every((input) => input.value);
      if (!selected || body.children.length === 0) {
        event.preventDefault();
        window.alert("Выберите существующий товар из списка.");
      }
    });
    (initial.length ? initial : [{}]).forEach(addLine);
  });
})();
