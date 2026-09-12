(() => {
  "use strict";

  function updateClock() {
    const now = new Date();
    const date = document.getElementById("gb-date");
    const time = document.getElementById("gb-time");
    if (date) date.textContent = new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" }).format(now);
    if (time) time.textContent = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(now);
  }

  function attachAutocomplete({ input, typeInput, idInput, suggestions, endpoint, warehouseId, warehouseInput, onSelect }) {
    if (!input || !typeInput || !idInput || !suggestions || !endpoint) return;
    let timer;
    const host = suggestions.parentElement;

    // Подсказки переносятся в body, чтобы таблица с горизонтальным overflow
    // не обрезала список и не создавала внутреннюю вертикальную прокрутку.
    const positionSuggestions = () => {
      if (!suggestions.classList.contains("open")) return;
      const rect = input.getBoundingClientRect();
      const viewportPadding = 8;
      const width = Math.min(rect.width, window.innerWidth - viewportPadding * 2);
      const left = Math.max(
        viewportPadding,
        Math.min(rect.left, window.innerWidth - width - viewportPadding),
      );
      const desiredHeight = Math.min(250, suggestions.scrollHeight);
      const spaceBelow = window.innerHeight - rect.bottom - viewportPadding;
      const spaceAbove = rect.top - viewportPadding;
      const openAbove = spaceBelow < Math.min(160, desiredHeight) && spaceAbove > spaceBelow;
      const maxHeight = Math.max(80, Math.min(250, openAbove ? spaceAbove : spaceBelow));

      suggestions.style.left = `${left}px`;
      suggestions.style.width = `${width}px`;
      suggestions.style.maxHeight = `${maxHeight}px`;
      suggestions.style.top = openAbove
        ? `${Math.max(viewportPadding, rect.top - Math.min(desiredHeight, maxHeight) - 4)}px`
        : `${rect.bottom + 4}px`;
    };
    const open = () => {
      if (suggestions.parentElement !== document.body) document.body.append(suggestions);
      suggestions.classList.add("autocomplete-portal", "open");
      positionSuggestions();
    };
    const close = () => {
      suggestions.classList.remove("open", "autocomplete-portal");
      suggestions.removeAttribute("style");
      suggestions.replaceChildren();
      if (host.isConnected) {
        if (suggestions.parentElement !== host) host.append(suggestions);
      } else {
        suggestions.remove();
      }
    };
    const selectResult = (result) => {
      input.value = result.label;
      typeInput.value = result.type;
      idInput.value = result.id;
      if (onSelect) onSelect(result);
      close();
    };
    const loadSuggestions = async (query) => {
      try {
        const selectedWarehouse = warehouseInput ? warehouseInput.value : warehouseId;
        const warehouseQuery = selectedWarehouse ? `&warehouse=${encodeURIComponent(selectedWarehouse)}` : "";
        const response = await fetch(`${endpoint}?q=${encodeURIComponent(query)}${warehouseQuery}`, { headers: { "X-Requested-With": "XMLHttpRequest" } });
        if (!response.ok || input.value.trim() !== query) return close();
        const payload = await response.json();
        const exactBarcodeMatches = payload.results.filter(
          (result) => String(result.barcode || "").trim() === query,
        );
        if (exactBarcodeMatches.length === 1) {
          selectResult(exactBarcodeMatches[0]);
          return;
        }
        suggestions.replaceChildren();
        payload.results.forEach((result) => {
          const option = document.createElement("button");
          option.type = "button";
          option.className = "suggestion";
          const label = document.createElement("span");
          label.textContent = result.label;
          const available = document.createElement("small");
          available.textContent = result.barcode
            ? `Штрихкод: ${result.barcode} · На складе: ${result.available}`
            : `На складе: ${result.available}`;
          option.append(label, available);
          option.addEventListener("click", () => selectResult(result));
          suggestions.append(option);
        });
        if (payload.results.length > 0) open();
        else close();
      } catch (_) {
        close();
      }
    };
    input.addEventListener("input", () => {
      typeInput.value = "";
      idInput.value = "";
      if (onSelect) onSelect(null);
      clearTimeout(timer);
      const query = input.value.trim();
      if (query.length < 2) return close();
      timer = setTimeout(() => loadSuggestions(query), 180);
    });
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || idInput.value) return;
      const query = input.value.trim();
      if (query.length < 2) return;
      event.preventDefault();
      clearTimeout(timer);
      loadSuggestions(query);
    });
    document.addEventListener("click", (event) => {
      if (!input.contains(event.target) && !suggestions.contains(event.target)) close();
    });
    window.addEventListener("resize", positionSuggestions);
    document.addEventListener("scroll", positionSuggestions, true);
  }

  function initExchangeRates() {
    const elements = [...document.querySelectorAll("[data-rate-symbol]")];
    if (!elements.length) return;

    const refresh = async () => {
      try {
        const response = await fetch("/api/exchange-rates/", {
          cache: "no-store",
          headers: { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest" },
        });
        if (!response.ok) return;
        const payload = await response.json();
        if (!payload || payload.available === false || typeof payload.rates !== "object") return;
        elements.forEach((element) => {
          const output = element.querySelector("b");
          const value = payload.rates[element.dataset.rateSymbol]?.value;
          if (!output) return;
          const numeric = Number(value);
          output.textContent = value !== null && value !== "" && Number.isFinite(numeric)
            ? numeric.toFixed(2)
            : "—";
        });
      } catch (_) {
        // Сохраняем последнее успешно показанное значение до следующей попытки.
      }
    };

    refresh();
    if (!window.__gamebatExchangeRateTimer) {
      window.__gamebatExchangeRateTimer = window.setInterval(refresh, 15000);
    }
  }

  updateClock();
  setInterval(updateClock, 1000);
  initExchangeRates();

  document.querySelectorAll(".product-operation-form").forEach((form) => {
    attachAutocomplete({
      input: form.querySelector("#id_product_search"),
      typeInput: form.querySelector("#id_product_type"),
      idInput: form.querySelector("#id_product_id"),
      suggestions: form.querySelector(".suggestions"),
      endpoint: form.dataset.autocompleteUrl,
      warehouseInput: form.querySelector("#id_warehouse"),
    });
  });

  document.querySelectorAll("[data-table-filter]").forEach((input) => {
    const body = document.getElementById(input.dataset.tableFilter);
    if (!body) return;
    input.addEventListener("input", () => {
      const query = input.value.trim().toLocaleLowerCase("ru-RU");
      body.querySelectorAll("tr").forEach((row) => {
        row.hidden = Boolean(query) && !row.textContent.toLocaleLowerCase("ru-RU").includes(query);
      });
    });
  });

  document.querySelectorAll("[data-product-filters]").forEach((form) => {
    const platform = form.querySelector('[data-product-filter="platform"]');
    const brand = form.querySelector('[data-product-filter="brand"]');
    const productType = form.querySelector('[data-product-filter="product_type"]');
    if (!platform || !brand || !productType) return;

    const syncFilters = (changed) => {
      if (changed === platform && platform.value) {
        brand.value = "";
        productType.value = "";
      } else if ((changed === brand || changed === productType) && changed.value) {
        platform.value = "";
      }
      const hasPlatform = Boolean(platform.value);
      const hasTechFilter = Boolean(brand.value || productType.value);
      platform.disabled = hasTechFilter;
      brand.disabled = hasPlatform;
      productType.disabled = hasPlatform;
    };

    [platform, brand, productType].forEach((select) => {
      select.addEventListener("change", () => syncFilters(select));
    });
    syncFilters(null);
  });

  document.querySelectorAll("[data-collapse-toggle]").forEach((button) => {
    const content = document.getElementById(button.getAttribute("aria-controls"));
    if (!content) return;
    button.addEventListener("click", () => {
      const expanded = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!expanded));
      content.hidden = expanded;
    });
  });

  document.querySelectorAll("[data-dialog-open]").forEach((button) => {
    const dialog = document.getElementById(button.dataset.dialogOpen);
    if (!dialog || typeof dialog.showModal !== "function") return;
    button.addEventListener("click", () => dialog.showModal());
    dialog.querySelectorAll("[data-dialog-close]").forEach((closeButton) => {
      closeButton.addEventListener("click", () => dialog.close());
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  });

  window.GameBAT = { attachAutocomplete };
})();
