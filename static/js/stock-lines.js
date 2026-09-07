(() => {
  "use strict";
  document.querySelectorAll(".stock-lines-form").forEach((form) => {
    const body = form.querySelector(".stock-lines");
    const add = form.querySelector(".add-stock-line");
    const initialNode = form.dataset.initialItemsId ? document.getElementById(form.dataset.initialItemsId) : null;
    const initial = initialNode ? JSON.parse(initialNode.textContent) : [];
    const warehouseInput = form.dataset.warehouseSelectId ? document.getElementById(form.dataset.warehouseSelectId) : null;

    function addLine(value = {}) {
      const row = document.createElement("tr");
      const productCell = document.createElement("td");
      const wrap = document.createElement("div");
      wrap.className = "autocomplete-wrap";
      const search = document.createElement("input");
      search.type = "text";
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

    add.addEventListener("click", () => addLine());
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
