(() => {
  "use strict";
  const form = document.getElementById("consignment-transfer-form");
  if (!form) return;
  const lines = document.getElementById("consignment-lines");
  const warehouse = document.getElementById("id_warehouse");
  const initialLines = JSON.parse(document.getElementById("initial-consignment-lines").textContent);

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
      onSelect: showCost,
    });
    if (!value.label) search.focus();
  }

  document.getElementById("add-consignment-line").addEventListener("click", addLine);
  form.addEventListener("submit", (event) => {
    const productIds = [...lines.querySelectorAll('input[name="product_id"]')];
    if (!productIds.length || !productIds.every((input) => input.value)) {
      event.preventDefault();
      window.alert(productIds.length ? "Выберите существующий товар из списка." : "Добавьте хотя бы один товар.");
    }
  });
  (initialLines.length ? initialLines : [{}]).forEach(addLine);
})();
