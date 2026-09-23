(() => {
  "use strict";

  const globalBarcodeHandlers = [];

  function registerGlobalBarcodeHandler(handler) {
    if (typeof handler !== "function") return () => {};
    globalBarcodeHandlers.push(handler);
    return () => {
      const index = globalBarcodeHandlers.lastIndexOf(handler);
      if (index >= 0) globalBarcodeHandlers.splice(index, 1);
    };
  }

  function scannerCanStartFrom(target) {
    if (!(target instanceof Element)) return true;
    if (target.matches("[data-global-barcode-search-input], [data-sale-barcode-input], [data-consignment-barcode-input]")) return true;
    if (target.matches("textarea, [contenteditable='true']")) return false;
    if (!target.matches("input")) return true;
    return ["number", "range", "checkbox", "radio", "button", "submit"].includes(target.type);
  }

  function captureControlState(target) {
    if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement)) {
      return null;
    }
    return {
      target,
      value: target.value,
      selectionStart: typeof target.selectionStart === "number" ? target.selectionStart : null,
      selectionEnd: typeof target.selectionEnd === "number" ? target.selectionEnd : null,
      className: target.className,
      title: target.getAttribute("title"),
    };
  }

  function restoreControlState(snapshot) {
    if (!snapshot || !snapshot.target.isConnected) return;
    const { target } = snapshot;
    target.value = snapshot.value;
    target.className = snapshot.className;
    if (snapshot.title === null) target.removeAttribute("title");
    else target.setAttribute("title", snapshot.title);
    if (snapshot.selectionStart !== null && typeof target.setSelectionRange === "function") {
      target.setSelectionRange(snapshot.selectionStart, snapshot.selectionEnd);
    }
    if (target instanceof HTMLInputElement && target.type === "number") {
      target.dispatchEvent(new Event("input", { bubbles: true }));
    } else if (target instanceof HTMLSelectElement) {
      target.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  function initGlobalBarcodeScanner() {
    let buffer = "";
    let startedAt = 0;
    let lastAt = 0;
    let largestGap = 0;
    let controlSnapshot = null;

    const reset = () => {
      buffer = "";
      startedAt = 0;
      lastAt = 0;
      largestGap = 0;
      controlSnapshot = null;
    };

    document.addEventListener("keydown", (event) => {
      if (!globalBarcodeHandlers.length || event.isComposing || event.repeat) return;
      if (event.ctrlKey || event.altKey || event.metaKey) {
        reset();
        return;
      }
      if (event.key === "Shift") return;
      const now = performance.now();
      if (event.key === "Enter") {
        const duration = Math.max(0, lastAt - startedAt);
        const averageGap = buffer.length > 1 ? duration / (buffer.length - 1) : Infinity;
        const isScanner = buffer.length >= 8 && largestGap <= 150 && averageGap <= 80;
        const barcode = buffer;
        const snapshot = controlSnapshot;
        reset();
        if (!isScanner) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        restoreControlState(snapshot);
        const handler = globalBarcodeHandlers[globalBarcodeHandlers.length - 1];
        Promise.resolve(handler(barcode)).catch(() => {});
        return;
      }
      if (event.key.length !== 1 || !/^[0-9A-Za-z._-]$/.test(event.key)) {
        reset();
        return;
      }
      if (!scannerCanStartFrom(event.target)) {
        reset();
        return;
      }
      const gap = lastAt ? now - lastAt : 0;
      if (!lastAt || gap > 150) {
        buffer = event.key;
        startedAt = now;
        largestGap = 0;
        controlSnapshot = captureControlState(event.target);
      } else {
        buffer += event.key;
        largestGap = Math.max(largestGap, gap);
      }
      lastAt = now;
    }, true);
  }

  function updateClock() {
    const now = new Date();
    const date = document.getElementById("gb-date");
    const time = document.getElementById("gb-time");
    if (date) date.textContent = new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" }).format(now);
    if (time) time.textContent = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(now);
  }

  function attachAutocomplete({
    input, typeInput, idInput, suggestions, endpoint, warehouseId, warehouseInput,
    searchContext, priceTypeInput, fixedPriceType, onSelect,
  }) {
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
    const selectResult = (result, metadata = {}) => {
      input.value = result.label;
      typeInput.value = result.type;
      idInput.value = result.id;
      if (onSelect) onSelect(result, metadata);
      close();
    };
    const loadSuggestions = async (query) => {
      try {
        const selectedWarehouse = warehouseInput ? warehouseInput.value : warehouseId;
        const params = new URLSearchParams({ q: query });
        if (selectedWarehouse) params.set("warehouse", selectedWarehouse);
        if (searchContext) params.set("context", searchContext);
        const selectedPriceType = priceTypeInput ? priceTypeInput.value : fixedPriceType;
        if (selectedPriceType) params.set("price_type", selectedPriceType);
        const response = await fetch(`${endpoint}?${params.toString()}`, { headers: { "X-Requested-With": "XMLHttpRequest" } });
        if (!response.ok || input.value.trim() !== query) return close();
        const payload = await response.json();
        const exactBarcodeMatches = payload.results.filter(
          (result) => (result.barcodes || [result.barcode]).some(
            (value) => String(value || "").trim() === query,
          ),
        );
        if (exactBarcodeMatches.length === 1) {
          selectResult(exactBarcodeMatches[0], { exactBarcode: true });
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
          const identifiers = [];
          if (result.sku) identifiers.push(`Арт.: ${result.sku}`);
          if (result.cusa_ppsa_code) identifiers.push(`CUSA/PPSA: ${result.cusa_ppsa_code}`);
          if (result.barcodes?.length) identifiers.push(`Штрихкоды: ${result.barcodes.join(", ")}`);
          else if (result.barcode) identifiers.push(`Штрихкод: ${result.barcode}`);
          identifiers.push(`${result.availability_label || "На складе"}: ${result.available}`);
          if (result.storage_locations) identifiers.push(`Место: ${result.storage_locations}`);
          available.textContent = identifiers.join(" · ");
          option.append(label, available);
          option.addEventListener("click", () => selectResult(result, { exactBarcode: false }));
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
          if (value === null || value === "" || !Number.isFinite(numeric)) return;
          const decimals = Number.parseInt(element.dataset.rateDecimals || "2", 10);
          output.textContent = numeric.toFixed(decimals);
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
  initGlobalBarcodeScanner();

  document.querySelectorAll(".product-operation-form").forEach((form) => {
    attachAutocomplete({
      input: form.querySelector("#id_product_search"),
      typeInput: form.querySelector("#id_product_type"),
      idInput: form.querySelector("#id_product_id"),
      suggestions: form.querySelector(".suggestions"),
      endpoint: form.dataset.autocompleteUrl,
      warehouseInput: form.querySelector("#id_warehouse"),
      searchContext: form.dataset.searchContext,
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
    const gameSeries = form.querySelector('[data-product-filter="game_series"]');
    const brand = form.querySelector('[data-product-filter="brand"]');
    const productType = form.querySelector('[data-product-filter="product_type"]');
    if (!platform || !brand || !productType) return;

    const syncFilters = (changed) => {
      if (changed === platform && platform.value) {
        brand.value = "";
        productType.value = "";
      // На некоторых страницах серии нет; при начальной синхронизации changed
      // тоже null. Проверка элемента нужна до чтения value, иначе сломается
      // дальнейшее подключение сворачивания и глобального сканера.
      } else if (gameSeries && changed === gameSeries && gameSeries.value) {
        brand.value = "";
        productType.value = "";
      } else if ((changed === brand || changed === productType) && changed.value) {
        platform.value = "";
        if (gameSeries) gameSeries.value = "";
      }
      const hasCdFilter = Boolean(platform.value || (gameSeries && gameSeries.value));
      const hasTechFilter = Boolean(brand.value || productType.value);
      platform.disabled = hasTechFilter;
      if (gameSeries) gameSeries.disabled = hasTechFilter;
      brand.disabled = hasCdFilter;
      productType.disabled = hasCdFilter;
    };

    [platform, gameSeries, brand, productType].filter(Boolean).forEach((select) => {
      select.addEventListener("change", () => syncFilters(select));
    });
    form.querySelector('[data-avito-highlight-toggle]')?.addEventListener("change", () => form.requestSubmit());
    form.querySelector('[data-zero-stock-highlight-toggle]')?.addEventListener("change", () => form.requestSubmit());
    syncFilters(null);
  });

  const globalBarcodeSearchForm = document.querySelector("[data-global-barcode-search]");
  if (globalBarcodeSearchForm) {
    const searchInput = globalBarcodeSearchForm.querySelector("[data-global-barcode-search-input]");
    if (searchInput) {
      registerGlobalBarcodeHandler((barcode) => {
        searchInput.value = barcode;
        globalBarcodeSearchForm.requestSubmit();
      });
    }
  }

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

  window.GameBAT = { attachAutocomplete, registerGlobalBarcodeHandler };
})();
