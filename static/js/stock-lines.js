(() => {
  "use strict";
  document.querySelectorAll(".stock-lines-form").forEach((form) => {
    const body = form.querySelector(".stock-lines");
    const add = form.querySelector(".add-stock-line");
    const initialNode = form.dataset.initialItemsId ? document.getElementById(form.dataset.initialItemsId) : null;
    const initial = initialNode ? JSON.parse(initialNode.textContent) : [];
    const warehouseInput = form.dataset.warehouseSelectId ? document.getElementById(form.dataset.warehouseSelectId) : null;
    const priceTypeInput = form.dataset.priceSelectId ? document.getElementById(form.dataset.priceSelectId) : null;
    const paymentInput = form.dataset.paymentSelectId ? document.getElementById(form.dataset.paymentSelectId) : null;
    const totalOutput = form.querySelector("[data-sale-intermediate-total]");
    const receivedContainer = form.querySelector("[data-cash-received-container]");
    const receivedInput = receivedContainer ? receivedContainer.querySelector("input") : null;
    const barcodeInput = form.querySelector("[data-sale-barcode-input]");
    const barcodeButton = form.querySelector("[data-sale-barcode-add]");
    const barcodeFeedback = form.querySelector("[data-sale-barcode-feedback]");
    const showSaleInventory = form.dataset.showSaleInventory === "true";
    const money = new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    let inventoryRequestNumber = 0;

    function selectedPrice(row) {
      if (row.dataset.fixedUnitPrice) return Number(row.dataset.fixedUnitPrice);
      const prices = row.dataset.prices ? JSON.parse(row.dataset.prices) : {};
      const priceType = priceTypeInput ? priceTypeInput.value : form.dataset.fixedPriceType;
      const value = prices[priceType];
      return value === null || value === undefined || value === "" ? null : Number(value);
    }

    function recalculate() {
      let total = 0;
      const selectedQuantities = new Map();
      if (showSaleInventory) {
        body.querySelectorAll("tr").forEach((row) => {
          const type = row.querySelector('input[name="product_type"]')?.value;
          const id = row.querySelector('input[name="product_id"]')?.value;
          if (!type || !id) return;
          const key = `${type}:${id}`;
          const quantity = Math.max(0, Number(row.querySelector('input[name="quantity"]')?.value || 0));
          selectedQuantities.set(key, (selectedQuantities.get(key) || 0) + quantity);
        });
      }
      body.querySelectorAll("tr").forEach((row) => {
        const quantityInput = row.querySelector('input[name="quantity"]');
        const quantity = Number(quantityInput?.value || 0);
        const price = selectedPrice(row);
        const priceOutput = row.querySelector("[data-unit-price]");
        const lineOutput = row.querySelector("[data-line-total]");
        if (priceOutput) priceOutput.textContent = Number.isFinite(price) ? `${money.format(price)} ₽` : "—";
        const lineTotal = Number.isFinite(price) && quantity > 0 ? price * quantity : 0;
        if (lineOutput) lineOutput.textContent = Number.isFinite(price) ? `${money.format(lineTotal)} ₽` : "—";
        total += lineTotal;
        if (showSaleInventory) {
          const stockOutput = row.querySelector("[data-warehouse-stock]");
          const availableOutput = row.querySelector("[data-available-more]");
          const locationOutput = row.querySelector("[data-storage-locations]");
          const errorOutput = row.querySelector("[data-stock-error]");
          const type = row.querySelector('input[name="product_type"]')?.value;
          const id = row.querySelector('input[name="product_id"]')?.value;
          const loaded = row.dataset.inventoryLoaded === "true";
          const stock = loaded ? Number(row.dataset.warehouseStock || 0) : null;
          const selected = type && id ? (selectedQuantities.get(`${type}:${id}`) || 0) : 0;
          const overStock = stock !== null && selected > stock;
          if (stockOutput) stockOutput.textContent = stock === null ? "—" : String(stock);
          if (availableOutput) availableOutput.textContent = stock === null ? "—" : String(Math.max(0, stock - selected));
          if (locationOutput) {
            locationOutput.textContent = stock === null
              ? "—"
              : (row.dataset.storageLocations || "Не указано");
          }
          if (errorOutput) {
            errorOutput.textContent = overStock ? `На выбранном складе доступно только ${stock} шт.` : "";
          }
          row.classList.toggle("sale-stock-invalid", overStock);
          row.dataset.stockInvalid = overStock ? "true" : "false";
          if (quantityInput) quantityInput.setCustomValidity(overStock ? `На выбранном складе доступно только ${stock} шт.` : "");
        }
      });
      if (totalOutput) totalOutput.textContent = `${money.format(total)} ₽`;
    }

    function applyInventory(row, result) {
      const hasWarehouseData = result && result.warehouse_stock !== null && result.warehouse_stock !== undefined;
      if (hasWarehouseData) {
        row.dataset.warehouseStock = String(Number(result.warehouse_stock) || 0);
        row.dataset.storageLocations = result.storage_locations || "";
        row.dataset.inventoryLoaded = "true";
      } else {
        delete row.dataset.warehouseStock;
        delete row.dataset.storageLocations;
        row.dataset.inventoryLoaded = "false";
      }
      recalculate();
    }

    async function refreshInventory() {
      if (!showSaleInventory) return;
      const requestNumber = ++inventoryRequestNumber;
      const rows = [...body.querySelectorAll("tr")];
      const selectedWarehouse = warehouseInput ? warehouseInput.value : form.dataset.warehouseId;
      if (!selectedWarehouse) {
        rows.forEach((row) => applyInventory(row, null));
        return;
      }
      const refs = [...new Set(rows.map((row) => {
        const type = row.querySelector('input[name="product_type"]')?.value;
        const id = row.querySelector('input[name="product_id"]')?.value;
        return type && id ? `${type}:${id}` : "";
      }).filter(Boolean))];
      if (!refs.length) {
        recalculate();
        return;
      }
      rows.forEach((row) => { row.dataset.inventoryLoaded = "false"; });
      recalculate();
      try {
        const params = new URLSearchParams({
          context: "sale",
          warehouse: selectedWarehouse,
          items: refs.join(","),
        });
        const response = await fetch(`${form.dataset.autocompleteUrl}?${params.toString()}`, {
          headers: { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest" },
        });
        if (!response.ok) throw new Error("Не удалось обновить остатки склада.");
        const payload = await response.json();
        if (requestNumber !== inventoryRequestNumber) return;
        const byProduct = new Map(payload.results.map((result) => [`${result.type}:${result.id}`, result]));
        rows.forEach((row) => {
          const type = row.querySelector('input[name="product_type"]')?.value;
          const id = row.querySelector('input[name="product_id"]')?.value;
          applyInventory(row, byProduct.get(`${type}:${id}`) || { warehouse_stock: 0, storage_locations: "" });
        });
      } catch (_) {
        if (requestNumber !== inventoryRequestNumber) return;
        rows.forEach((row) => applyInventory(row, null));
      }
    }

    function syncCashReceivedVisibility() {
      if (!receivedContainer || !paymentInput) return;
      const visible = paymentInput.value === "cash";
      receivedContainer.hidden = !visible;
      if (receivedInput) receivedInput.disabled = !visible;
    }

    function addLine(value = {}) {
      const row = document.createElement("tr");
      const productCell = document.createElement("td");
      const wrap = document.createElement("div");
      wrap.className = "autocomplete-wrap";
      const search = document.createElement("input");
      search.type = "text";
      search.dataset.productSearch = "true";
      search.placeholder = "Название, артикул, CUSA/PPSA или штрихкод";
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

      const priceCell = document.createElement("td");
      priceCell.className = "numeric readonly-money";
      priceCell.dataset.unitPrice = "true";
      const quantityCell = document.createElement("td");
      const quantity = document.createElement("input");
      quantity.type = "number";
      quantity.name = "quantity";
      quantity.min = "1";
      quantity.step = "1";
      quantity.required = true;
      quantity.value = value.quantity || "";
      quantityCell.append(quantity);
      const stockError = document.createElement("span");
      stockError.className = "error-text sale-line-stock-error";
      stockError.dataset.stockError = "true";
      quantityCell.append(stockError);
      const lineTotalCell = document.createElement("td");
      lineTotalCell.className = "numeric readonly-money";
      lineTotalCell.dataset.lineTotal = "true";
      const stockCell = document.createElement("td");
      stockCell.className = "numeric sale-inventory-value";
      stockCell.dataset.warehouseStock = "true";
      const availableCell = document.createElement("td");
      availableCell.className = "numeric sale-inventory-value";
      availableCell.dataset.availableMore = "true";
      const locationCell = document.createElement("td");
      locationCell.className = "sale-storage-location";
      locationCell.dataset.storageLocations = "true";
      if (value.unit_price !== undefined && value.unit_price !== "") row.dataset.fixedUnitPrice = value.unit_price;
      else if (value.prices) row.dataset.prices = JSON.stringify(value.prices);

      const removeCell = document.createElement("td");
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "remove-row";
      remove.setAttribute("aria-label", "Удалить строку");
      remove.textContent = "×";
      remove.addEventListener("click", () => {
        row.remove();
        recalculate();
      });
      removeCell.append(remove);
      row.append(productCell, priceCell, quantityCell, lineTotalCell);
      if (showSaleInventory) row.append(stockCell, availableCell, locationCell);
      row.append(removeCell);
      body.append(row);
      quantity.addEventListener("input", recalculate);
      window.GameBAT.attachAutocomplete({
        input: search,
        typeInput: type,
        idInput: id,
        suggestions,
        endpoint: form.dataset.autocompleteUrl,
        warehouseId: form.dataset.warehouseId,
        warehouseInput,
        searchContext: form.dataset.searchContext,
        priceTypeInput,
        fixedPriceType: form.dataset.fixedPriceType,
        onSelect: (result, metadata = {}) => {
          delete row.dataset.fixedUnitPrice;
          row.dataset.prices = result?.prices ? JSON.stringify(result.prices) : "{}";
          if (
            result && warehouseInput && !warehouseInput.value
            && Array.isArray(result.available_warehouse_ids)
            && result.available_warehouse_ids.length === 1
          ) {
            warehouseInput.value = String(result.available_warehouse_ids[0]);
            warehouseInput.dispatchEvent(new Event("change", {bubbles: true}));
          }
          applyInventory(row, result);
          if (result && metadata.exactBarcode) {
            if (!quantity.value) quantity.value = "1";
            recalculate();
            if (barcodeFeedback) {
              barcodeFeedback.classList.remove("error-text");
              barcodeFeedback.textContent = `Добавлено: ${result.label}`;
            }
            quantity.focus();
          }
        },
      });
      if (showSaleInventory && Object.prototype.hasOwnProperty.call(value, "warehouse_stock")) {
        applyInventory(row, value);
      } else {
        recalculate();
      }
      if (!value.label) search.focus();
    }

    function putBarcodeResultIntoSale(result) {
      const existingRow = [...body.querySelectorAll("tr")].find((row) => (
        row.querySelector('input[name="product_type"]')?.value === String(result.type)
        && row.querySelector('input[name="product_id"]')?.value === String(result.id)
      ));
      if (existingRow) {
        const quantity = existingRow.querySelector('input[name="quantity"]');
        if (quantity) {
          quantity.value = String(Math.max(0, Number(quantity.value) || 0) + 1);
          quantity.dispatchEvent(new Event("input", { bubbles: true }));
          quantity.focus();
        }
        return;
      }
      const blankRow = [...body.querySelectorAll("tr")].find((row) => {
        const productId = row.querySelector('input[name="product_id"]');
        const productSearch = row.querySelector("[data-product-search]");
        return productId && productSearch && !productId.value && !productSearch.value.trim();
      });
      if (blankRow) {
        blankRow.querySelector("[data-product-search]").value = result.label;
        blankRow.querySelector('input[name="product_type"]').value = result.type;
        blankRow.querySelector('input[name="product_id"]').value = result.id;
        blankRow.dataset.prices = JSON.stringify(result.prices || {});
        delete blankRow.dataset.fixedUnitPrice;
        const quantity = blankRow.querySelector('input[name="quantity"]');
        if (quantity && !quantity.value) quantity.value = "1";
        applyInventory(blankRow, result);
        if (quantity) quantity.focus();
        return;
      }
      addLine({
        label: result.label,
        product_type: result.type,
        product_id: result.id,
        quantity: 1,
        prices: result.prices,
        warehouse_stock: result.warehouse_stock,
        storage_locations: result.storage_locations,
      });
    }

    async function addByBarcode(scannedBarcode = "") {
      if (!barcodeInput || !barcodeFeedback) return;
      const barcode = String(scannedBarcode || barcodeInput.value).trim();
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
        const params = new URLSearchParams({
          q: barcode,
          warehouse: selectedWarehouse,
          context: form.dataset.searchContext || "sale",
        });
        const priceType = priceTypeInput ? priceTypeInput.value : form.dataset.fixedPriceType;
        if (priceType) params.set("price_type", priceType);
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
        if (exactMatches.length === 0) throw new Error("Товар с таким штрихкодом не найден.");
        if (exactMatches.length > 1) {
          throw new Error("Этот штрихкод указан у нескольких товаров. Выберите товар через обычный поиск.");
        }
        const result = exactMatches[0];
        if (Number(result.available) <= 0) throw new Error("Этого товара нет на выбранном складе.");
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
    if (barcodeInput && barcodeFeedback && window.GameBAT.registerGlobalBarcodeHandler) {
      window.GameBAT.registerGlobalBarcodeHandler(addByBarcode);
    }
    if (priceTypeInput) priceTypeInput.addEventListener("change", recalculate);
    if (warehouseInput) warehouseInput.addEventListener("change", refreshInventory);
    if (paymentInput) paymentInput.addEventListener("change", syncCashReceivedVisibility);
    form.addEventListener("submit", (event) => {
      const selected = [...body.querySelectorAll('input[name="product_id"]')].every((input) => input.value);
      if (!selected || body.children.length === 0) {
        event.preventDefault();
        window.alert("Выберите существующий товар из списка.");
        return;
      }
      if (showSaleInventory && [...body.querySelectorAll("tr")].some((row) => row.dataset.stockInvalid === "true")) {
        event.preventDefault();
        window.alert("Количество товара превышает остаток выбранного склада.");
        return;
      }
      if (paymentInput?.value === "cash" && receivedInput?.value) {
        const currentTotal = [...body.querySelectorAll("tr")].reduce((sum, row) => {
          const price = selectedPrice(row);
          const quantity = Number(row.querySelector('input[name="quantity"]')?.value || 0);
          return sum + (Number.isFinite(price) ? price * quantity : 0);
        }, 0);
        if (Number(receivedInput.value) < currentTotal) {
          event.preventDefault();
          window.alert("Полученная сумма не может быть меньше стоимости продажи.");
        }
      }
    });
    (initial.length ? initial : [{}]).forEach(addLine);
    syncCashReceivedVisibility();
    recalculate();
    refreshInventory();
  });
})();
