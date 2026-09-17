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
  const csrfToken = form.querySelector('input[name="csrfmiddlewaretoken"]').value;

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
    const weightPrompt = document.createElement("div");
    weightPrompt.className = "supply-weight-prompt";
    weightPrompt.hidden = true;
    wrap.append(search, type, id, suggestionBox, weightPrompt);
    productCell.append(wrap);

    function hideWeightPrompt() {
      weightPrompt.hidden = true;
      weightPrompt.replaceChildren();
      row.classList.remove("supply-line-needs-weight");
    }

    function requestProductWeight(result) {
      hideWeightPrompt();
      if (!result || Number(result.weight_grams) > 0) return;
      id.value = "";
      row.classList.add("supply-line-needs-weight");
      weightPrompt.hidden = false;
      const label = document.createElement("label");
      label.textContent = "Введите вес товара, г";
      const controls = document.createElement("div");
      controls.className = "supply-weight-controls";
      const input = document.createElement("input");
      input.type = "number";
      input.min = "1";
      input.step = "1";
      input.inputMode = "numeric";
      const save = document.createElement("button");
      save.type = "button";
      save.className = "button button-small";
      save.textContent = "Сохранить и добавить";
      const feedback = document.createElement("span");
      feedback.className = "error-text";
      if (result.can_set_weight === false) {
        input.disabled = true;
        save.disabled = true;
        feedback.textContent = "Нет права изменять вес товара. Обратитесь к администратору.";
      }
      save.addEventListener("click", async () => {
        feedback.textContent = "";
        if (!/^\d+$/.test(input.value.trim()) || Number(input.value) < 1) {
          feedback.textContent = "Введите целый вес не меньше 1 г.";
          return;
        }
        save.disabled = true;
        try {
          const payload = new URLSearchParams({
            product_type: result.type,
            product_id: result.id,
            weight_grams: input.value.trim(),
            csrfmiddlewaretoken: csrfToken,
          });
          const response = await fetch(form.dataset.weightUrl, {
            method: "POST",
            body: payload,
            headers: { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest" },
          });
          const data = await response.json().catch(() => ({}));
          if (!response.ok || !data.ok) throw new Error(data.error || "Не удалось сохранить вес.");
          type.value = result.type;
          id.value = result.id;
          result.weight_grams = data.weight_grams;
          hideWeightPrompt();
          cost.focus();
        } catch (error) {
          feedback.textContent = error.message;
          save.disabled = false;
        }
      });
      input.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        save.click();
      });
      controls.append(input, save);
      weightPrompt.append(label, controls, feedback);
      input.focus();
    }

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
    window.GameBAT.attachAutocomplete({
      input: search,
      typeInput: type,
      idInput: id,
      suggestions: suggestionBox,
      endpoint: form.dataset.autocompleteUrl,
      warehouseInput: warehouse,
      searchContext: form.dataset.searchContext,
      onSelect: requestProductWeight,
    });
    if (value.product_id && !value.weight_grams) {
      requestProductWeight({
        id: value.product_id,
        type: value.product_type,
        weight_grams: value.weight_grams,
        can_set_weight: value.can_set_weight !== false,
      });
    }
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
      return;
    }
    if (form.dataset.editing === "true") {
      const confirmed = document.getElementById("revision-confirmed");
      const dialog = document.getElementById("supply-revision-dialog");
      if (confirmed && confirmed.value !== "1") {
        event.preventDefault();
        dialog.showModal();
      }
    }
  });
  const revisionDialog = document.getElementById("supply-revision-dialog");
  if (revisionDialog) {
    revisionDialog.querySelector("[data-revision-cancel]").addEventListener("click", () => revisionDialog.close());
    revisionDialog.querySelector("[data-revision-confirm]").addEventListener("click", () => {
      document.getElementById("revision-confirmed").value = "1";
      revisionDialog.close();
      form.requestSubmit();
    });
  }
  (initialLines.length ? initialLines : [{}]).forEach(addProductLine);
  (initialExpenses.length ? initialExpenses : [{}]).forEach(addExpenseLine);
})();
