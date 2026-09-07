(() => {
  "use strict";
  const form = document.getElementById("supply-form");
  if (!form) return;
  const suppliers = JSON.parse(document.getElementById("supplier-data").textContent);
  const initialLines = JSON.parse(document.getElementById("initial-supply-lines").textContent);
  const initialExpenses = JSON.parse(document.getElementById("initial-expense-lines").textContent);
  const lines = document.getElementById("supply-lines");
  const expenses = document.getElementById("expense-lines");
  const warehouse = document.getElementById("id_warehouse");

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

  function addProductLine(value = {}) {
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

    const supplierCell = document.createElement("td");
    const supplierSelect = document.createElement("select");
    supplierSelect.name = "supplier_id";
    supplierSelect.required = true;
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Выберите поставщика";
    supplierSelect.append(placeholder);
    suppliers.forEach((supplier) => {
      const option = document.createElement("option");
      option.value = supplier.id;
      option.textContent = supplier.label;
      supplierSelect.append(option);
    });
    supplierSelect.value = value.supplier_id || "";
    supplierCell.append(supplierSelect);

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
    const cost = document.createElement("input");
    cost.type = "number";
    cost.name = "purchase_unit_cost";
    cost.min = "0";
    cost.step = "0.000001";
    cost.required = true;
    cost.value = value.purchase_unit_cost || "";
    costCell.append(cost);

    row.append(productCell, supplierCell, quantityCell, costCell, removeButton(row));
    lines.append(row);
    window.GameBAT.attachAutocomplete({ input: search, typeInput: type, idInput: id, suggestions: suggestionBox, endpoint: form.dataset.autocompleteUrl, warehouseInput: warehouse });
    if (!value.label) search.focus();
  }

  function addExpenseLine(value = {}) {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    const name = document.createElement("input");
    name.type = "text";
    name.name = "expense_name";
    name.placeholder = "Например, доставка";
    name.value = value.name || "";
    nameCell.append(name);
    const amountCell = document.createElement("td");
    const amount = document.createElement("input");
    amount.type = "number";
    amount.name = "expense_amount";
    amount.min = "0";
    amount.step = "0.01";
    amount.value = value.amount || "";
    amountCell.append(amount);
    row.append(nameCell, amountCell, removeButton(row));
    expenses.append(row);
  }

  document.getElementById("add-line").addEventListener("click", addProductLine);
  document.getElementById("add-expense").addEventListener("click", addExpenseLine);
  form.addEventListener("submit", (event) => {
    const selected = [...lines.querySelectorAll('input[name="product_id"]')].every((input) => input.value);
    if (!selected) {
      event.preventDefault();
      window.alert("Выберите существующий товар из списка.");
    }
  });
  (initialLines.length ? initialLines : [{}]).forEach(addProductLine);
  (initialExpenses.length ? initialExpenses : [{}]).forEach(addExpenseLine);
})();
