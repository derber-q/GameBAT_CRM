(() => {
  "use strict";
  document.querySelectorAll(".stock-lines-form").forEach((form) => {
    const body = form.querySelector(".stock-lines");
    const addButtons = form.querySelectorAll(".add-stock-line");
    const add = addButtons[0];
    let addCustom = form.querySelector(".add-custom-line");
    if (!addCustom && add) {
      addCustom = document.createElement("button");
      addCustom.type = "button";
      addCustom.className = "button button-secondary button-small add-custom-line";
      addCustom.textContent = "+ Добавить произвольный товар";
      add.parentElement.appendChild(addCustom);
    }
    const consignmentNode = document.getElementById("consignment-sale-options");
    const consignmentOptions = consignmentNode ? JSON.parse(consignmentNode.textContent) : [];
    const addConsignmentButtons = [];
    form.querySelectorAll(".add-custom-line").forEach((customButton) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "button button-secondary button-small add-consignment-line";
      button.textContent = "+ Добавить реализацию";
      customButton.parentElement.appendChild(button);
      addConsignmentButtons.push(button);
    });
    const initialNode = form.dataset.initialItemsId ? document.getElementById(form.dataset.initialItemsId) : null;
    const initial = initialNode ? JSON.parse(initialNode.textContent) : [];
    const warehouseInput = form.dataset.warehouseSelectId ? document.getElementById(form.dataset.warehouseSelectId) : null;
    const priceTypeInput = form.dataset.priceSelectId ? document.getElementById(form.dataset.priceSelectId) : null;
    const paymentInput = form.dataset.paymentSelectId ? document.getElementById(form.dataset.paymentSelectId) : null;
    const saleTypeInput = form.dataset.saleTypeSelectId ? document.getElementById(form.dataset.saleTypeSelectId) : null;
    const totalOutput = form.querySelector("[data-sale-intermediate-total]");
    const commissionOutput = form.querySelector("[data-sale-commission-total]");
    const netTotalOutput = form.querySelector("[data-sale-net-total]");
    const commissionSummaryRows = form.querySelectorAll("[data-avito-commission-summary]");
    const commissionColumns = form.querySelectorAll("[data-avito-commission-column]");
    const receivedContainer = form.querySelector("[data-cash-received-container]");
    const receivedInput = receivedContainer ? receivedContainer.querySelector("input") : null;
    const barcodeInput = form.querySelector("[data-sale-barcode-input]");
    const barcodeButton = form.querySelector("[data-sale-barcode-add]");
    const barcodeFeedback = form.querySelector("[data-sale-barcode-feedback]");
    const showSaleInventory = form.dataset.showSaleInventory === "true";
    const wholeMoney = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
    function cents(raw) {
      const match = String(raw ?? "").trim().replace(",", ".").match(/^(-?)(\d+)(?:\.(\d{1,2}))?$/);
      if (!match) return null;
      const value = BigInt(match[2]) * 100n + BigInt((match[3] || "").padEnd(2, "0"));
      return match[1] ? -value : value;
    }
    function decimalMoney(value) {
      const absolute = value < 0n ? -value : value;
      return `${value < 0n ? "-" : ""}${absolute / 100n}.${String(absolute % 100n).padStart(2, "0")}`;
    }
    function formatMoney(value) {
      const absolute = value < 0n ? -value : value;
      return `${value < 0n ? "−" : ""}${wholeMoney.format(absolute / 100n)},${String(absolute % 100n).padStart(2, "0")}`;
    }
    function moneyQuantity(input) {
      const value = String(input?.value || "");
      return /^\d+$/.test(value) ? BigInt(value) : 0n;
    }
    let inventoryRequestNumber = 0;

    const mixedMessage = "Цифровые товары и расходы необходимо оформлять отдельной продажей.";
    function rowMode(row) {
      if (row.dataset.systemKind) return row.dataset.systemKind;
      if (row.classList.contains("sale-custom-line") || row.classList.contains("sale-consignment-line") || row.querySelector('input[name="product_id"]')?.value) return "normal";
      return null;
    }
    function allowMode(mode, exceptRow = null) {
      const incompatible = [...body.querySelectorAll("tr")].some(row => row !== exceptRow && rowMode(row) && rowMode(row) !== mode);
      if (incompatible) {
        if (barcodeFeedback) { barcodeFeedback.textContent = mixedMessage; barcodeFeedback.classList.add("error-text"); }
        return false;
      }
      return true;
    }
    function operationMode() {
      return [...body.querySelectorAll("tr")].map(rowMode).find(Boolean) || "normal";
    }

    function isAvitoSale() {
      return operationMode() !== "EXPENSE" && (saleTypeInput ? saleTypeInput.value : form.dataset.fixedSaleType) === "avito";
    }

    function labelSaleRow(row) {
      if (form.dataset.searchContext !== "sale") return;
      const fields = [
        ["product", "Товар / штрихкод"], ["price", "Базовая цена"],
        ["discount", "Скидка / доплата, ед."], ["quantity", "Количество"],
        ["cost", "Себестоимость"], ["total", "Сумма строки"],
        ["commission", "Комиссия Avito"],
        ...(showSaleInventory ? [["stock", "Остаток на складе"], ["available", "Доступно ещё"], ["location", "Место хранения"]] : []),
        ["remove", ""],
      ];
      [...row.children].forEach((cell, index) => {
        const [field, label] = fields[index];
        cell.dataset.saleField = field;
        cell.dataset.saleLabel = label;
        cell.querySelectorAll('input:not([type="hidden"]), select').forEach((input) => {
          if (!input.hasAttribute("aria-label")) input.setAttribute("aria-label", label);
        });
      });
    }

    function addCommissionControl(cell, hiddenName) {
      const control = document.createElement("span");
      control.className = "sale-avito-commission-control";
      control.dataset.avitoCommissionControl = "true";
      const hidden = document.createElement("input");
      hidden.type = "hidden";
      hidden.name = hiddenName;
      hidden.value = isAvitoSale() ? "1" : "0";
      hidden.dataset.avitoCommissionFlag = "true";
      const preview = document.createElement("small");
      preview.className = "help-text";
      preview.dataset.avitoCommissionPreview = "true";
      control.append(hidden, preview);
      cell.dataset.avitoCommissionColumn = "true";
      cell.hidden = !isAvitoSale();
      cell.append(control);
    }

    function syncCommissionVisibility() {
      const visible = isAvitoSale();
      commissionSummaryRows.forEach((row) => { row.hidden = !visible; });
      commissionColumns.forEach((column) => { column.hidden = !visible; });
      body.querySelectorAll("[data-avito-commission-column]").forEach((column) => {
        column.hidden = !visible;
      });
      body.querySelectorAll("[data-avito-commission-control]").forEach((control) => {
        control.hidden = !visible;
        const hidden = control.querySelector("[data-avito-commission-flag]");
        if (hidden) hidden.value = visible ? "1" : "0";
      });
    }

    function selectedBasePrice(row) {
      if (row.classList.contains("sale-custom-line")) {
        const value = row.querySelector('input[name="custom_unit_price"]')?.value;
        return cents(value);
      }
      if (row.dataset.fixedUnitPrice) return cents(row.dataset.fixedUnitPrice);
      const prices = row.dataset.prices ? JSON.parse(row.dataset.prices) : {};
      const priceType = priceTypeInput ? priceTypeInput.value : form.dataset.fixedPriceType;
      const value = prices[priceType];
      return cents(value);
    }

    function addConsignmentLine(value = {}) {
      if (!allowMode("normal")) return;
      const row = document.createElement("tr");
      row.className = "sale-consignment-line";
      const productCell = document.createElement("td");
      const select = document.createElement("select");
      select.required = true;
      const empty = new Option("Выберите площадку и товар", "");
      select.append(empty);
      consignmentOptions.forEach((option) => {
        const element = new Option(option.label, `${option.kind}:${option.stock_id}`);
        element.dataset.kind = option.kind;
        element.dataset.stockId = option.stock_id;
        element.dataset.quantity = option.quantity;
        element.dataset.unitPrice = option.unit_price;
        select.append(element);
      });
      const initialValue = value.stock_id ? `${value.product_kind}:${value.stock_id}` : "";
      if (initialValue && ![...select.options].some((option) => option.value === initialValue)) {
        const historical = new Option(value.label || "Историческая партия реализации", initialValue);
        historical.dataset.kind = value.product_kind;
        historical.dataset.stockId = value.stock_id;
        historical.dataset.quantity = value.quantity || 0;
        historical.dataset.unitPrice = value.unit_price || 0;
        select.append(historical);
      }
      select.value = initialValue;
      const kind = document.createElement("input"); kind.type = "hidden"; kind.name = "consignment_product_type";
      const stockId = document.createElement("input"); stockId.type = "hidden"; stockId.name = "consignment_stock_id";
      productCell.append(select, kind, stockId);
      const priceCell = document.createElement("td"); priceCell.className = "numeric readonly-money"; priceCell.dataset.unitPrice = "true";
      const discountCell = document.createElement("td"); discountCell.className = "numeric muted"; discountCell.textContent = "—";
      const quantityCell = document.createElement("td");
      const quantity = document.createElement("input"); quantity.type = "number"; quantity.name = "consignment_quantity";
      quantity.min = "1"; quantity.step = "1"; quantity.required = true; quantity.value = value.quantity || "1";
      quantityCell.append(quantity);
      const costCell = document.createElement("td"); costCell.className = "numeric muted"; costCell.textContent = "—";
      const totalCell = document.createElement("td"); totalCell.className = "numeric readonly-money"; totalCell.dataset.lineTotal = "true";
      const commissionCell = document.createElement("td");
      commissionCell.className = "numeric muted";
      commissionCell.dataset.avitoCommissionColumn = "true";
      commissionCell.hidden = !isAvitoSale();
      commissionCell.textContent = "—";
      const inventoryCells = showSaleInventory ? [document.createElement("td"), document.createElement("td"), document.createElement("td")] : [];
      const removeCell = document.createElement("td");
      const remove = document.createElement("button"); remove.type = "button"; remove.className = "remove-row"; remove.textContent = "×";
      remove.addEventListener("click", () => { row.remove(); recalculate(); }); removeCell.append(remove);
      const applySelection = () => {
        const option = select.selectedOptions[0];
        kind.value = option?.dataset.kind || "";
        stockId.value = option?.dataset.stockId || "";
        row.dataset.fixedUnitPrice = option?.dataset.unitPrice || value.unit_price || "";
        recalculate();
      };
      select.addEventListener("change", applySelection); quantity.addEventListener("input", recalculate);
      row.append(productCell, priceCell, discountCell, quantityCell, costCell, totalCell, commissionCell, ...inventoryCells, removeCell);
      labelSaleRow(row);
      body.append(row); applySelection();
    }

    function selectedPrice(row) {
      const base = selectedBasePrice(row);
      if (base === null) return null;
      const discountInput = row.classList.contains("sale-custom-line")
        ? row.querySelector('input[name="custom_unit_discount"]')
        : row.querySelector('input[name="unit_discount"]');
      const discount = cents(discountInput?.value || "0");
      return discount === null ? null : base - discount;
    }

    function addDiscountControl(cell, name, initialValue) {
      const control = document.createElement("div");
      control.className = "sale-discount-control";
      const sign = document.createElement("select");
      sign.dataset.discountSign = "true";
      sign.setAttribute("aria-label", "Скидка или доплата за единицу");
      for (const [value, label] of [["-", "−"], ["+", "+"]]) {
        const option = document.createElement("option");
        option.value = value; option.textContent = label;
        sign.append(option);
      }
      const amount = document.createElement("input");
      amount.type = "number"; amount.min = "0"; amount.step = "0.01"; amount.required = true;
      amount.dataset.discountAmount = "true";
      amount.setAttribute("aria-label", "Сумма скидки или доплаты за единицу");
      const signed = document.createElement("input");
      signed.type = "hidden"; signed.name = name;
      const initial = cents(initialValue || "0") ?? 0n;
      sign.value = initial < 0n ? "+" : "-";
      amount.value = decimalMoney(initial < 0n ? -initial : initial);
      const sync = () => {
        const value = cents(amount.value);
        signed.value = value === null ? "" : decimalMoney(sign.value === "+" ? -value : value);
        sign.title = sign.value === "+" ? "Доплата за единицу товара" : "Скидка за единицу товара";
        recalculate();
      };
      sign.addEventListener("change", sync);
      amount.addEventListener("input", sync);
      control.append(sign, amount, signed); cell.append(control);
      signed.value = decimalMoney(initial);
      sign.title = sign.value === "+" ? "Доплата за единицу товара" : "Скидка за единицу товара";
    }

    function addCustomLine(value = {}) {
      const systemKind = value.system_kind || "";
      if (!allowMode(systemKind || "normal")) return;
      const row = document.createElement("tr");
      row.className = "sale-custom-line";
      if (systemKind) row.dataset.systemKind = systemKind;
      const nameCell = document.createElement("td");
      const name = document.createElement("input");
      name.type = "text"; name.name = "custom_name"; name.required = true;
      name.placeholder = "Название товара или услуги"; name.value = value.name || "";
      nameCell.append(name);
      const kindInput = document.createElement("input");
      kindInput.type = "hidden"; kindInput.name = "custom_system_kind"; kindInput.value = systemKind;
      nameCell.append(kindInput);
      if (systemKind) {
        name.value = systemKind === "EXPENSE" ? "Расход" : "Цифровой товар";
        name.readOnly = true;
      }
      const priceCell = document.createElement("td");
      const price = document.createElement("input");
      price.type = "number"; price.name = "custom_unit_price"; price.min = "0"; price.step = "0.01"; price.required = true;
      price.placeholder = "\u0426\u0435\u043d\u0430";
      price.value = value.unit_price || ""; priceCell.append(price);
      if (systemKind === "EXPENSE") { price.value = "0"; price.readOnly = true; }
      const discountCell = document.createElement("td");
      addDiscountControl(discountCell, "custom_unit_discount", value.unit_discount);
      if (systemKind) {
        discountCell.querySelectorAll("input, select").forEach(input => { input.value = input.type === "hidden" ? "0.00" : input.value; input.disabled = input.type !== "hidden"; });
      }
      const quantityCell = document.createElement("td");
      const quantity = document.createElement("input");
      quantity.type = "number"; quantity.name = "custom_quantity"; quantity.min = "1"; quantity.step = "1"; quantity.required = true;
      quantity.value = value.quantity || "1"; quantityCell.append(quantity);
      const costCell = document.createElement("td");
      const cost = document.createElement("input");
      cost.type = "number"; cost.name = "custom_unit_cost"; cost.min = "0"; cost.step = "0.01"; cost.required = true;
      cost.placeholder = "\u0421\u0435\u0431\u0435\u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c";
      cost.value = value.unit_cost || ""; costCell.append(cost);
      const totalCell = document.createElement("td"); totalCell.className = "numeric readonly-money"; totalCell.dataset.lineTotal = "true";
      const commissionCell = document.createElement("td"); commissionCell.className = "numeric readonly-money";
      addCommissionControl(commissionCell, "custom_avito_commission_enabled");
      const inventoryCells = showSaleInventory ? [document.createElement("td"), document.createElement("td"), document.createElement("td")] : [];
      const removeCell = document.createElement("td");
      const remove = document.createElement("button"); remove.type = "button"; remove.className = "remove-row"; remove.textContent = "×";
      remove.setAttribute("aria-label", "Удалить произвольную позицию"); remove.addEventListener("click", () => { row.remove(); recalculate(); });
      removeCell.append(remove); row.append(nameCell, priceCell, discountCell, quantityCell, costCell, totalCell, commissionCell, ...inventoryCells, removeCell); body.append(row);
      if (systemKind) {
        discountCell.hidden = true;
        inventoryCells.forEach(cell => { cell.hidden = true; });
      }
      labelSaleRow(row);
      [price, quantity, cost, name].forEach((input) => input.addEventListener("input", recalculate));
      recalculate();
      return row;
    }

    function recalculate() {
      const note = form.querySelector('[name="note"]');
      const digital = operationMode() === "DIGITAL_PRODUCT";
      const noteHelp = form.querySelector("[data-system-note-help]");
      if (noteHelp) noteHelp.hidden = !digital;
      const operationHelp = form.querySelector("[data-sale-operation-help]");
      if (operationHelp) operationHelp.textContent = operationMode() === "EXPENSE"
        ? "Расход уменьшит прибыль в статистике после завершения операции. Деньги из кассы не списываются."
        : "Наличная продажа сразу пополнит кассу; остальные создадут неоплаченный заказ.";
      const hasAdjustment = [...body.querySelectorAll('input[name="unit_discount"], input[name="custom_unit_discount"]')].some(input => (cents(input.value || "0") ?? 0n) !== 0n);
      if (note) {
        note.required = digital || hasAdjustment;
        note.setAttribute("aria-required", String(note.required));
        note.setAttribute("placeholder", digital ? "Обязательно: укажите, какой цифровой товар продан." : "Примечание к продаже");
      }
      syncCashReceivedVisibility();
      syncCommissionVisibility();
      let total = 0n;
      let totalCommission = 0n;
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
        const quantityInput = row.classList.contains("sale-custom-line")
          ? row.querySelector('input[name="custom_quantity"]')
          : (row.classList.contains("sale-consignment-line")
            ? row.querySelector('input[name="consignment_quantity"]')
            : row.querySelector('input[name="quantity"]'));
        const quantity = moneyQuantity(quantityInput);
        const basePrice = selectedBasePrice(row);
        const price = selectedPrice(row);
        const priceOutput = row.querySelector("[data-unit-price]");
        const lineOutput = row.querySelector("[data-line-total]");
        if (priceOutput) priceOutput.textContent = basePrice !== null ? `${formatMoney(basePrice)} ₽` : "—";
        const lineTotal = price !== null && quantity > 0n ? price * quantity : 0n;
        if (lineOutput) lineOutput.textContent = price !== null ? `${formatMoney(lineTotal)} ₽` : "—";
        const commissionFlag = row.querySelector("[data-avito-commission-flag]");
        const commissionPreview = row.querySelector("[data-avito-commission-preview]");
        const commissionEnabled = isAvitoSale() && Boolean(commissionFlag);
        const roundedCommission = (lineTotal + 100n) / 200n;
        const commission = commissionEnabled && price !== null && quantity > 0n
          ? (roundedCommission > 100n ? roundedCommission : 100n) : 0n;
        totalCommission += commission;
        if (commissionFlag) commissionFlag.value = commissionEnabled ? "1" : "0";
        if (commissionPreview) {
          commissionPreview.textContent = `${formatMoney(commission)} ₽`;
        }
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
      if (totalOutput) totalOutput.textContent = `${formatMoney(total)} ₽`;
      if (commissionOutput) commissionOutput.textContent = `${formatMoney(totalCommission)} ₽`;
      if (netTotalOutput) netTotalOutput.textContent = `${formatMoney(total - totalCommission)} ₽`;
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
      const visible = paymentInput.value === "cash" && operationMode() !== "EXPENSE";
      receivedContainer.hidden = !visible;
      if (receivedInput) receivedInput.disabled = !visible;
    }

    function addLine(value = {}) {
      if (value.custom) { addCustomLine(value); return; }
      if (value.consignment) { addConsignmentLine(value); return; }
      if (!allowMode("normal")) return;
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
      const fullName = document.createElement("span");
      fullName.className = "sale-product-full-name";
      fullName.textContent = value.label || "";
      if (form.dataset.searchContext === "sale") {
        productCell.append(fullName);
        search.addEventListener("input", () => { fullName.textContent = ""; });
      }

      const priceCell = document.createElement("td");
      priceCell.className = "numeric readonly-money";
      priceCell.dataset.unitPrice = "true";
      const discountCell = document.createElement("td");
      addDiscountControl(discountCell, "unit_discount", value.unit_discount);
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
      const costCell = document.createElement("td");
      costCell.className = "numeric readonly-money";
      const lineTotalCell = document.createElement("td");
      lineTotalCell.className = "numeric readonly-money";
      lineTotalCell.dataset.lineTotal = "true";
      const commissionCell = document.createElement("td");
      commissionCell.className = "numeric readonly-money";
      addCommissionControl(commissionCell, "avito_commission_enabled");
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
      row.append(productCell, priceCell, discountCell, quantityCell, costCell, lineTotalCell, commissionCell);
      if (showSaleInventory) row.append(stockCell, availableCell, locationCell);
      row.append(removeCell);
      labelSaleRow(row);
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
          if (result?.type === "system") {
            if (!allowMode(result.system_kind || result.id, row)) { type.value = ""; id.value = ""; search.value = ""; return; }
            row.remove();
            [...body.querySelectorAll("tr")].filter(candidate => !rowMode(candidate)).forEach(candidate => candidate.remove());
            const special = addCustomLine({system_kind: result.system_kind || result.id});
            special?.querySelector('input[name="custom_unit_cost"]')?.focus();
            return;
          }
          if (result && !allowMode("normal", row)) { type.value = ""; id.value = ""; search.value = ""; return; }
          fullName.textContent = result?.label || "";
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
            focusBarcodeQuantity(quantity);
          }
        },
      });
      if (showSaleInventory && Object.prototype.hasOwnProperty.call(value, "warehouse_stock")) {
        applyInventory(row, value);
      } else {
        recalculate();
      }
      if (!value.label) search.focus();
      return row;
    }

    function focusBarcodeQuantity(quantity) {
      if (!quantity) return;
      quantity.focus({ preventScroll: true });
      quantity.scrollIntoView({ block: "nearest", inline: "nearest" });
    }

    function putBarcodeResultIntoSale(result) {
      const mode = result.type === "system" ? (result.system_kind || result.id) : "normal";
      if (!allowMode(mode)) throw new Error(mixedMessage);
      if (result.type === "system") {
        [...body.querySelectorAll("tr")].filter(row => !rowMode(row)).forEach(row => row.remove());
        const row = addCustomLine({system_kind: mode});
        return row.querySelector('input[name="custom_quantity"]');
      }
      const existingRow = [...body.querySelectorAll("tr")].find((row) => (
        row.querySelector('input[name="product_type"]')?.value === String(result.type)
        && row.querySelector('input[name="product_id"]')?.value === String(result.id)
      ));
      if (existingRow) {
        const quantity = existingRow.querySelector('input[name="quantity"]');
        if (quantity) {
          quantity.value = String(Math.max(0, Number(quantity.value) || 0) + 1);
          quantity.dispatchEvent(new Event("input", { bubbles: true }));
        }
        return quantity;
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
        return quantity;
      }
      const row = addLine({
        label: result.label,
        product_type: result.type,
        product_id: result.id,
        quantity: 1,
        prices: result.prices,
        warehouse_stock: result.warehouse_stock,
        storage_locations: result.storage_locations,
      });
      return row.querySelector('input[name="quantity"]');
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
        if (result.type !== "system" && Number(result.available) <= 0) throw new Error("Этого товара нет на выбранном складе.");
        const quantity = putBarcodeResultIntoSale(result);
        barcodeInput.value = "";
        barcodeFeedback.textContent = `Добавлено: ${result.label}`;
        focusBarcodeQuantity(quantity);
      } catch (error) {
        barcodeFeedback.textContent = error.message;
        barcodeFeedback.classList.add("error-text");
      }
    }

    addButtons.forEach((button) => button.addEventListener("click", () => addLine()));
    form.querySelectorAll(".add-custom-line").forEach((button) => button.addEventListener("click", () => addCustomLine()));
    addConsignmentButtons.forEach((button) => button.addEventListener("click", () => addConsignmentLine()));
    if (barcodeButton) barcodeButton.addEventListener("click", () => addByBarcode());
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
    if (saleTypeInput) saleTypeInput.addEventListener("change", () => {
      syncCommissionVisibility();
      recalculate();
    });
    if (warehouseInput) warehouseInput.addEventListener("change", refreshInventory);
    if (paymentInput) paymentInput.addEventListener("change", syncCashReceivedVisibility);
    form.addEventListener("submit", (event) => {
      const productRows = [...body.querySelectorAll("tr")].filter((row) => (
        !row.classList.contains("sale-custom-line") && !row.classList.contains("sale-consignment-line")
      ));
      const selected = productRows.every((row) => {
        const id = row.querySelector('input[name="product_id"]');
        const search = row.querySelector("[data-product-search]");
        return !id || (!search?.value.trim() && !id.value) || Boolean(id.value);
      });
      const customValid = [...body.querySelectorAll('input[name="custom_name"]')].every((input) => input.value.trim());
      if ((!selected || !customValid) || body.children.length === 0) {
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
          const quantity = moneyQuantity(row.classList.contains("sale-custom-line")
            ? row.querySelector('input[name="custom_quantity"]')
            : (row.classList.contains("sale-consignment-line")
              ? row.querySelector('input[name="consignment_quantity"]')
              : row.querySelector('input[name="quantity"]')));
          return sum + (price !== null ? price * quantity : 0n);
        }, 0n);
        const received = cents(receivedInput.value);
        if (received !== null && received < currentTotal) {
          event.preventDefault();
          window.alert("Полученная сумма не может быть меньше стоимости продажи.");
        }
      }
      const hasDiscount = [...body.querySelectorAll('input[name="unit_discount"], input[name="custom_unit_discount"]')]
        .some((input) => (cents(input.value || "0") ?? 0n) !== 0n);
      const noteInput = form.querySelector('[name="note"]');
      if ((hasDiscount || operationMode() === "DIGITAL_PRODUCT") && noteInput && !noteInput.value.trim()) {
        event.preventDefault();
        window.alert(operationMode() === "DIGITAL_PRODUCT" ? "Для продажи цифрового товара необходимо заполнить примечание." : "При использовании скидки или доплаты обязательно укажите примечание к продаже.");
        noteInput.focus();
      }
    });
    (initial.length ? initial : [{}]).forEach(addLine);
    syncCashReceivedVisibility();
    syncCommissionVisibility();
    recalculate();
    refreshInventory();
  });
})();
