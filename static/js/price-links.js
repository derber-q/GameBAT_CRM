document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy-link]");
  if (!button) return;
  const input = button.parentElement.querySelector("input");
  if (!input) return;
  const label = button.textContent;
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(input.value);
    } else {
      input.focus();
      input.select();
      if (!document.execCommand("copy")) throw new Error("copy");
    }
    button.textContent = "Скопировано";
  } catch {
    input.focus();
    input.select();
    button.textContent = "Выделено — скопируйте вручную";
  }
  setTimeout(() => { button.textContent = label; }, 1600);
});
