document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector(".resource-storefront");
  if (!root) return;
  root.classList.add("rs-js");
  const $ = selector => root.querySelector(selector);
  let lockedY = null;
  function lock() {
    lockedY = window.scrollY;
    document.body.style.position = "fixed";
    document.body.style.top = -lockedY + "px";
    document.body.style.width = "100%";
  }
  function unlock() {
    document.body.style.position = "";
    document.body.style.top = "";
    document.body.style.width = "";
    if (lockedY !== null) window.scrollTo(0, lockedY);
    lockedY = null;
  }
  const toast = $(".rs-toast");
  let toastTimer;
  function announce(text) {
    toast.textContent = text; toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, 7000);
  }
  function counts(value) {
    root.querySelectorAll("[data-cart-count]").forEach(el => { el.textContent = value; });
  }
  const nav = $("#rs-nav"), navDialog = $("#rs-nav-dialog");
  const menu = $(".mobile-menu"), searchOpen = $(".rs-search-open");
  if (nav && navDialog) {
    let opener;
    const header = $(".rs-header");
    const openNav = button => {
      opener = button; lock(); navDialog.append(nav); nav.classList.add("is-open");
      navDialog.showModal(); menu.setAttribute("aria-expanded", "true");
      (button === searchOpen ? $("#rs-search") : $(".rs-nav-close")).focus();
    };
    menu.addEventListener("click", () => openNav(menu));
    searchOpen.addEventListener("click", () => openNav(searchOpen));
    $(".rs-nav-close").addEventListener("click", () => navDialog.close());
    navDialog.addEventListener("close", () => {
      header.append(nav); nav.classList.remove("is-open"); unlock();
      menu.setAttribute("aria-expanded", "false"); opener?.focus();
    });
    window.matchMedia("(min-width:851px)").addEventListener("change", e => { if (e.matches && navDialog.open) navDialog.close(); });
  }
  root.querySelectorAll("[data-product-photo]").forEach(img => {
    const fallback = () => {
      img.hidden = true;
      const placeholder = img.parentElement.querySelector(".rs-placeholder");
      if (placeholder) placeholder.hidden = false;
    };
    img.addEventListener("error", fallback);
    if (img.complete && !img.naturalWidth) fallback();
  });
  function quantityState(group) {
    const input = group.querySelector("input");
    group.querySelector('[data-quantity-step="-1"]').disabled = !input.validity.valid || Number(input.value) <= Number(input.min);
    group.querySelector('[data-quantity-step="1"]').disabled = !input.validity.valid || Number(input.value) >= Number(input.max);
  }
  root.querySelectorAll(".rs-quantity").forEach(quantityState);
  root.addEventListener("click", event => {
    const button = event.target.closest("[data-quantity-step]");
    if (!button) return;
    const group = button.closest(".rs-quantity"), input = group.querySelector("input");
    if (button.dataset.quantityStep === "1") input.stepUp(); else input.stepDown();
    quantityState(group);
  });
  root.addEventListener("input", event => {
    if (event.target.closest(".rs-quantity")) quantityState(event.target.closest(".rs-quantity"));
  });
  const form = $("#rs-catalog-form"), category = $("#id_category");
  const filterDialog = $("#rs-filter-dialog"), panel = $("#rs-filters"), slot = $(".rs-filter-slot");
  const filterOpen = $(".rs-filter-open");
  let snapshot = null, applying = false;
  function applicable(clear = false) {
    if (!category) return;
    root.querySelectorAll("[data-filter-kind]").forEach(group => {
      const hidden = category.value && ((category.value === "cd") !== (group.dataset.filterKind === "cd"));
      group.hidden = Boolean(hidden);
      group.querySelectorAll("select").forEach(field => {
        field.disabled = Boolean(hidden);
        if (clear) field.value = "";
      });
    });
  }
  if (form) {
    applicable();
    category.addEventListener("change", () => applicable(true));
    $("#id_sort").addEventListener("change", () => form.requestSubmit());
    form.addEventListener("submit", () => { applying = true; form.setAttribute("aria-busy", "true"); });
    filterOpen.addEventListener("click", () => {
      snapshot = Array.from(form.elements).filter(el => el.name).map(el => [el, el.value]);
      applying = false; lock(); filterDialog.append(panel); filterDialog.showModal();
      filterOpen.setAttribute("aria-expanded", "true"); $(".rs-filter-close").focus();
    });
    $(".rs-filter-close").addEventListener("click", () => filterDialog.close());
    filterDialog.addEventListener("close", () => {
      if (!applying && snapshot) snapshot.forEach(([el, value]) => { el.value = value; });
      applicable(); slot.append(panel); unlock();
      filterOpen.setAttribute("aria-expanded", "false"); filterOpen.focus();
    });
    window.matchMedia("(min-width:1051px)").addEventListener("change", e => { if (e.matches && filterDialog.open) filterDialog.close(); });
  }
  const searches = [$("#rs-search"), $("#id_q")].filter(Boolean);
  searches.forEach(input => input.addEventListener("input", () => searches.forEach(other => { other.value = input.value; })));
  const scrollKey = "resource-scroll:" + location.pathname + location.search;
  window.addEventListener("pagehide", () => { try { sessionStorage.setItem(scrollKey, String(window.scrollY)); } catch {} });
  window.addEventListener("pageshow", () => {
    root.querySelectorAll('[aria-busy="true"]').forEach(el => el.removeAttribute("aria-busy"));
  });
  try {
    const saved = sessionStorage.getItem(scrollKey);
    if (saved && !location.hash) requestAnimationFrame(() => window.scrollTo(0, Number(saved)));
  } catch {}
  function communicationFields() {
    const checkout = $(".rs-checkout-form");
    if (!checkout || root.dataset.mode !== "retail") return;
    const telegram = checkout.querySelector('[name="communication"][value="telegram"]')?.checked;
    const whatsapp = checkout.querySelector('[name="communication"][value="whatsapp"]')?.checked;
    const usePhone = checkout.querySelector('[name="telegram_use_phone"]')?.checked;
    for (const [name, visible] of [["telegram_use_phone", telegram], ["telegram", telegram && !usePhone], ["whatsapp", whatsapp]]) {
      const field = checkout.querySelector('[data-checkout-field="' + name + '"]');
      if (field) { field.hidden = !visible; field.querySelectorAll("input").forEach(el => { el.disabled = !visible; }); }
    }
  }
  root.addEventListener("change", communicationFields);
  communicationFields();
  function draft() {
    const checkout = $(".rs-checkout-form");
    if (!checkout) return {};
    const result = {};
    Array.from(checkout.elements).filter(el => el.name && !["csrfmiddlewaretoken", "cart_version"].includes(el.name)).forEach(el => {
      if (el.type === "checkbox") { result[el.name] ||= []; if (el.checked) result[el.name].push(el.value); }
      else result[el.name] = el.value;
    });
    return result;
  }
  function restoreDraft(values) {
    const checkout = $(".rs-checkout-form");
    if (checkout) Array.from(checkout.elements).forEach(el => {
      if (!(el.name in values)) return;
      if (el.type === "checkbox") el.checked = Array.isArray(values[el.name]) && values[el.name].includes(el.value);
      else el.value = values[el.name];
    });
    communicationFields();
  }
  const draftPrefix = "resource-draft:" + (root.dataset.mode || "wholesale") + ":";
  const draftKey = draftPrefix + root.dataset.contact;
  try {
    const previousContact = sessionStorage.getItem(draftPrefix + "owner");
    if (previousContact !== root.dataset.contact) {
      if (previousContact) sessionStorage.removeItem(draftPrefix + previousContact);
      sessionStorage.setItem(draftPrefix + "owner", root.dataset.contact);
    }
    if ($(".rs-success")) sessionStorage.removeItem(draftKey);
    else restoreDraft(JSON.parse(sessionStorage.getItem(draftKey) || "{}"));
  } catch {}
  root.addEventListener("input", event => {
    if (event.target.closest(".rs-checkout-form")) {
      const field = event.target.closest(".rs-field");
      if (field) {
        const error = field.querySelector(".rs-field-error");
        if (error) error.textContent = "";
        event.target.removeAttribute("aria-invalid");
      }
      try { sessionStorage.setItem(draftKey, JSON.stringify(draft())); } catch {}
    }
  });
  let checkoutObserver;
  function observeCheckout() {
    checkoutObserver?.disconnect();
    const checkout = $("#rs-checkout");
    if (checkout && typeof IntersectionObserver !== "undefined") {
      checkoutObserver = new IntersectionObserver(entries => root.classList.toggle("rs-checkout-visible", entries[0].isIntersecting));
      checkoutObserver.observe(checkout);
    }
  }
  observeCheckout();
  async function request(url, options = {}) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(url, {credentials: "same-origin", cache: "no-store", signal: controller.signal, ...options,
        headers: {"X-Requested-With": "XMLHttpRequest", ...options.headers}});
      if (!response.headers.get("content-type")?.includes("application/json")) throw new Error("Не удалось получить ответ сервера.");
      return {response, data: await response.json()};
    } finally { clearTimeout(timer); }
  }
  let cartBusy = false;
  root.addEventListener("submit", async event => {
    const target = event.target;
    if (!target.matches("[data-cart-add], [data-cart-edit], .rs-checkout-form")) return;
    event.preventDefault();
    if (cartBusy || target.dataset.pending === "true") return;
    const checkout = target.matches(".rs-checkout-form");
    if (checkout && target.dataset.uncertain === "true") return;
    cartBusy = true; target.dataset.pending = "true"; target.setAttribute("aria-busy", "true");
    const buttons = Array.from(target.querySelectorAll("button")).map(el => [el, el.disabled]);
    buttons.forEach(([el]) => { el.disabled = true; });
    const body = new FormData(target), values = draft(), y = window.scrollY;
    if (target.matches("[data-cart-add]")) {
      target.dataset.operation ||= (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36));
      body.set("operation", target.dataset.operation);
    }
    const status = target.querySelector(".rs-form-status");
    if (status) status.textContent = "Оформляем заказ…";
    target.querySelectorAll("[data-error-for]").forEach(el => { el.textContent = ""; });
    try {
      const {response, data} = await request(target.action, {method: "POST", body});
      if (data.url) { try { sessionStorage.removeItem(draftKey); } catch {} location.assign(data.url); return; }
      if (data.cart_count !== undefined) counts(data.cart_count);
      if (!response.ok) {
        if (response.status >= 500) throw new Error("Результат операции неизвестен.");
        if (status) status.textContent = data.error;
        else announce(data.error);
        Object.entries(data.fields || {}).forEach(([key, errors]) => {
          const el = target.querySelector('[data-error-for="' + key + '"]');
          if (el) el.textContent = errors.join(" ");
        });
        if (data.refresh) target.querySelector(".rs-reload-cart").hidden = false;
      } else if (target.matches("[data-cart-add]")) {
        delete target.dataset.operation; announce(data.message);
      } else {
        $("#rs-cart-content").innerHTML = data.html; restoreDraft(values);
        observeCheckout();
        window.scrollTo(0, y); announce("Корзина обновлена");
      }
    } catch {
      if (checkout) {
        target.dataset.uncertain = "true";
        status.textContent = "Связь прервана. Проверьте статус заказа перед повторной попыткой.";
        target.querySelector(".rs-status-check").hidden = false;
      } else announce("Связь прервана. Повторите действие после подключения; корзина сохранена.");
    } finally {
      cartBusy = false; target.dataset.pending = "false"; target.removeAttribute("aria-busy");
      buttons.forEach(([el, disabled]) => { el.disabled = disabled; });
      if (target.dataset.uncertain === "true") target.querySelector('[type="submit"]').disabled = true;
    }
  });
  root.addEventListener("click", async event => {
    const button = event.target.closest(".rs-status-check");
    if (!button) return;
    const checkout = button.closest("form"), status = checkout.querySelector(".rs-form-status");
    button.disabled = true;
    try {
      const {response, data} = await request(checkout.dataset.statusUrl);
      if (!response.ok) { status.textContent = data.error; return; }
      if (data.url) { location.assign(data.url); return; }
      status.textContent = "Заказ пока не найден. Можно повторить оформление: используется тот же номер операции.";
      checkout.dataset.uncertain = "false"; checkout.querySelector('[type="submit"]').disabled = false;
    } catch { status.textContent = "Нет связи. Проверьте статус после подключения."; }
    finally { button.disabled = false; }
  });
  const viewport = window.visualViewport;
  const viewportSize = () => {
    root.style.setProperty("--rs-view-height", (viewport?.height || window.innerHeight) + "px");
    root.classList.toggle("rs-keyboard", Boolean(viewport && window.innerHeight - viewport.height > 150));
  };
  viewport?.addEventListener("resize", viewportSize); viewportSize();
});
