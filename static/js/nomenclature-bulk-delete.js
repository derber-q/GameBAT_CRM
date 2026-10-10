(() => {
  "use strict";

  const root = document.querySelector("[data-nomenclature-bulk]");
  const mode = root?.querySelector("[data-bulk-mode]");
  if (!mode) return;

  const products = Array.from(root.querySelectorAll("[data-bulk-product]"));
  const groups = Array.from(root.querySelectorAll("[data-bulk-group]"), (checkbox) => ({
    checkbox,
    products: Array.from(checkbox.closest("table").querySelectorAll("[data-bulk-product]")),
  }));
  const cells = root.querySelectorAll("[data-bulk-cell], [data-bulk-column]");
  const actions = root.querySelector("[data-bulk-actions]");
  const count = root.querySelector("[data-bulk-count]");
  const selectAll = root.querySelector("[data-bulk-select-all]");
  const clear = root.querySelector("[data-bulk-clear]");
  const open = root.querySelector("[data-bulk-open]");
  const dialog = root.querySelector("[data-bulk-dialog]");
  const form = root.querySelector("[data-bulk-form]");
  const submit = root.querySelector("[data-bulk-submit]");
  const selection = root.querySelector("[data-bulk-selection]");
  const preview = root.querySelector("[data-bulk-preview]");
  const cancel = root.querySelector("[data-bulk-cancel]");
  let submitting = false;

  function selected() {
    return mode.checked ? products.filter((checkbox) => checkbox.checked) : [];
  }

  function updateSelection() {
    const total = selected().length;
    count.textContent = `Выбрано: ${total}`;
    open.disabled = total === 0 || submitting;
    clear.disabled = total === 0 || submitting;
    selectAll.disabled = products.length === 0 || submitting;
    for (const checkbox of products) {
      checkbox.closest("tr").classList.toggle("bulk-selected", mode.checked && checkbox.checked);
    }
    for (const group of groups) {
      const checked = group.products.filter((checkbox) => checkbox.checked).length;
      group.checkbox.checked = checked > 0 && checked === group.products.length;
      group.checkbox.indeterminate = checked > 0 && checked < group.products.length;
      group.checkbox.disabled = group.products.length === 0 || !mode.checked || submitting;
    }
  }

  function setMode() {
    root.toggleAttribute("data-bulk-enabled", mode.checked);
    actions.hidden = !mode.checked;
    for (const cell of cells) cell.hidden = !mode.checked;
    for (const checkbox of products) {
      checkbox.disabled = !mode.checked || submitting;
      if (!mode.checked) checkbox.checked = false;
    }
    if (!mode.checked && dialog.open) dialog.close();
    selection.value = "";
    updateSelection();
  }

  function reset() {
    submitting = false;
    mode.disabled = false;
    mode.checked = false;
    submit.disabled = false;
    cancel.disabled = false;
    submit.textContent = "Да, удалить выбранные";
    if (dialog.open) dialog.close();
    setMode();
  }

  mode.addEventListener("change", setMode);
  for (const checkbox of products) checkbox.addEventListener("change", updateSelection);
  for (const group of groups) {
    group.checkbox.addEventListener("change", () => {
      for (const checkbox of group.products) checkbox.checked = group.checkbox.checked;
      updateSelection();
    });
  }
  selectAll.addEventListener("click", () => {
    for (const checkbox of products) checkbox.checked = true;
    updateSelection();
  });
  clear.addEventListener("click", () => {
    for (const checkbox of products) checkbox.checked = false;
    updateSelection();
  });
  open.addEventListener("click", () => {
    const items = selected();
    if (!items.length || submitting) return;
    const fragment = document.createDocumentFragment();
    for (const checkbox of items) {
      const item = document.createElement("li");
      const [kind, id] = checkbox.value.split(":");
      item.textContent = `${checkbox.dataset.productName} (${kind.toUpperCase()} #${id})`;
      fragment.append(item);
    }
    preview.replaceChildren(fragment);
    root.querySelector("[data-bulk-dialog-count]").textContent = String(items.length);
    dialog.showModal();
    cancel.focus();
  });
  cancel.addEventListener("click", () => dialog.close());
  dialog.addEventListener("cancel", (event) => {
    if (submitting) event.preventDefault();
  });
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog || submitting) return;
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right ||
        event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
  });
  form.addEventListener("submit", (event) => {
    const items = selected();
    if (!dialog.open || !items.length || submitting) {
      event.preventDefault();
      return;
    }
    // Один JSON-параметр позволяет выбрать более 1000 карточек без лимита POST-полей.
    selection.value = JSON.stringify(items.map((checkbox) => checkbox.value));
    submitting = true;
    submit.disabled = true;
    submit.textContent = "Удаление…";
    cancel.disabled = true;
  });

  reset();
  // Возврат назад и восстановление браузером формы не включают опасный режим повторно.
  window.addEventListener("pageshow", reset);
})();
