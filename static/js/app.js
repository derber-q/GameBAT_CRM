(() => {
  "use strict";

  function updateClock() {
    const now = new Date();
    const date = document.getElementById("gb-date");
    const time = document.getElementById("gb-time");
    if (date) date.textContent = new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" }).format(now);
    if (time) time.textContent = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(now);
  }

  function attachAutocomplete({ input, typeInput, idInput, suggestions, endpoint }) {
    if (!input || !typeInput || !idInput || !suggestions || !endpoint) return;
    let timer;
    const close = () => { suggestions.classList.remove("open"); suggestions.replaceChildren(); };
    input.addEventListener("input", () => {
      typeInput.value = "";
      idInput.value = "";
      clearTimeout(timer);
      const query = input.value.trim();
      if (query.length < 2) return close();
      timer = setTimeout(async () => {
        try {
          const response = await fetch(`${endpoint}?q=${encodeURIComponent(query)}`, { headers: { "X-Requested-With": "XMLHttpRequest" } });
          if (!response.ok) return close();
          const payload = await response.json();
          suggestions.replaceChildren();
          payload.results.forEach((result) => {
            const option = document.createElement("button");
            option.type = "button";
            option.className = "suggestion";
            const label = document.createElement("span");
            label.textContent = result.label;
            const available = document.createElement("small");
            available.textContent = `На складе: ${result.available}`;
            option.append(label, available);
            option.addEventListener("click", () => {
              input.value = result.label;
              typeInput.value = result.type;
              idInput.value = result.id;
              close();
            });
            suggestions.append(option);
          });
          suggestions.classList.toggle("open", payload.results.length > 0);
        } catch (_) {
          close();
        }
      }, 180);
    });
    document.addEventListener("click", (event) => {
      if (!suggestions.parentElement.contains(event.target)) close();
    });
  }

  updateClock();
  setInterval(updateClock, 1000);

  document.querySelectorAll(".product-operation-form").forEach((form) => {
    attachAutocomplete({
      input: form.querySelector("#id_product_search"),
      typeInput: form.querySelector("#id_product_type"),
      idInput: form.querySelector("#id_product_id"),
      suggestions: form.querySelector(".suggestions"),
      endpoint: form.dataset.autocompleteUrl,
    });
  });

  window.GameBAT = { attachAutocomplete };
})();
