(() => {
  "use strict";

  const ERROR = "Некорректный формат места хранения";
  const MAX_NUMBER = 2147483647;
  const LOCATION_PATTERN = /^([A-Za-z])\s*(\d+)\s*-\s*(\d+)(?:\s*-\s*(\d+(?:\s*\\\s*\d+)*))?$/;

  function normalizeLocationList(rawValue) {
    const value = String(rawValue || "").replace(/[–—]/g, "-").trim();
    if (!value) return "";
    const tokens = value.split(",");
    if (tokens.some((token) => !token.trim())) throw new Error(ERROR);
    const seen = new Set();
    const normalized = [];
    tokens.forEach((token) => {
      const match = token.trim().match(LOCATION_PATTERN);
      if (!match) throw new Error(ERROR);
      const rack = Number(match[2]);
      const shelf = Number(match[3]);
      const columns = match[4]
        ? [...new Set(match[4].split("\\").map((part) => Number(part.trim())))].sort((left, right) => left - right)
        : [];
      if (!Number.isSafeInteger(rack) || !Number.isSafeInteger(shelf)
          || rack <= 0 || shelf <= 0 || rack > MAX_NUMBER || shelf > MAX_NUMBER
          || columns.some((column) => !Number.isSafeInteger(column) || column <= 0 || column > MAX_NUMBER)) {
        throw new Error(ERROR);
      }
      let canonical = `${match[1].toUpperCase()}${rack}-${shelf}`;
      if (columns.length) canonical += `-${columns.join("\\")}`;
      if (!seen.has(canonical)) {
        seen.add(canonical);
        normalized.push(canonical);
      }
    });
    return normalized.join(", ");
  }

  function replaceLastToken(input, suggestion) {
    const comma = input.value.lastIndexOf(",");
    input.value = comma < 0
      ? suggestion
      : `${input.value.slice(0, comma).trim()}, ${suggestion}`;
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function attachSuggestions(input, suggestions, endpoint) {
    if (!input || !suggestions || !endpoint) return;
    let timer;
    const host = suggestions.parentElement;
    const position = () => {
      if (!suggestions.classList.contains("open")) return;
      const rect = input.getBoundingClientRect();
      suggestions.style.left = `${rect.left}px`;
      suggestions.style.top = `${rect.bottom + 4}px`;
      suggestions.style.width = `${Math.max(rect.width, 190)}px`;
      suggestions.style.maxHeight = `${Math.max(80, Math.min(250, window.innerHeight - rect.bottom - 12))}px`;
    };
    const open = () => {
      if (suggestions.parentElement !== document.body) document.body.append(suggestions);
      suggestions.classList.add("autocomplete-portal", "open");
      position();
    };
    const close = () => {
      suggestions.classList.remove("open", "autocomplete-portal");
      suggestions.removeAttribute("style");
      suggestions.replaceChildren();
      if (host.isConnected && suggestions.parentElement !== host) host.append(suggestions);
    };
    input.addEventListener("input", () => {
      clearTimeout(timer);
      const query = input.value.slice(input.value.lastIndexOf(",") + 1).trim();
      if (!query) return close();
      timer = window.setTimeout(async () => {
        try {
          const response = await fetch(`${endpoint}?q=${encodeURIComponent(input.value)}`, {
            headers: { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest" },
          });
          if (!response.ok) return close();
          const payload = await response.json();
          suggestions.replaceChildren();
          payload.results.forEach((result) => {
            const option = document.createElement("button");
            option.type = "button";
            option.className = "suggestion";
            option.textContent = result.label;
            option.addEventListener("click", () => {
              replaceLastToken(input, result.value);
              close();
              input.focus();
            });
            suggestions.append(option);
          });
          if (payload.results.length > 0) open();
          else close();
        } catch (_) {
          close();
        }
      }, 180);
    });
    document.addEventListener("click", (event) => {
      if (!input.contains(event.target) && !suggestions.contains(event.target)) close();
    });
    window.addEventListener("resize", position);
    document.addEventListener("scroll", position, true);
  }

  document.querySelectorAll("[data-storage-location-form]").forEach((form) => {
    const input = form.querySelector("[data-storage-location-input]");
    const button = form.querySelector('button[type="submit"]');
    const error = form.querySelector("[data-storage-location-error]");
    const feedback = form.querySelector("[data-storage-location-feedback]");
    const suggestions = form.querySelector(".storage-location-suggestions");

    const validate = () => {
      try {
        normalizeLocationList(input.value);
        form.classList.remove("has-error");
        error.hidden = true;
        button.disabled = false;
        return true;
      } catch (_) {
        form.classList.add("has-error");
        error.textContent = ERROR;
        error.hidden = false;
        button.disabled = true;
        return false;
      }
    };
    input.addEventListener("input", () => {
      feedback.textContent = "";
      validate();
    });
    attachSuggestions(input, suggestions, form.dataset.autocompleteUrl);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!validate()) return;
      input.value = normalizeLocationList(input.value);
      button.disabled = true;
      feedback.textContent = "Сохранение…";
      try {
        const response = await fetch(form.action, {
          method: "POST",
          body: new FormData(form),
          headers: { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest" },
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) throw new Error(payload.error || "Не удалось сохранить место хранения.");
        input.value = payload.value;
        feedback.textContent = payload.message;
        form.classList.remove("has-error");
        error.hidden = true;
      } catch (requestError) {
        form.classList.add("has-error");
        error.textContent = requestError.message;
        error.hidden = false;
        feedback.textContent = "";
      } finally {
        button.disabled = false;
      }
    });
    validate();
  });

  document.querySelectorAll("[data-storage-location-autocomplete]").forEach((input) => {
    attachSuggestions(
      input,
      input.parentElement.querySelector(".storage-location-suggestions"),
      input.dataset.autocompleteUrl,
    );
  });
})();
