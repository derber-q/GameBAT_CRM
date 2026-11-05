/* ReSOURCE: Расчётные поля закупочного прайса, наценка/постоплата и серверное подтверждение изменений. */
document.addEventListener("DOMContentLoaded", () => {
  const maxMoney = 99999999999999999999n;
  const parseMoney = (value, signed = false) => {
    const text = String(value).trim().replace(",", ".");
    if (!(signed ? /^-?\d+(?:\.\d{0,2})?$/ : /^\d+(?:\.\d{0,2})?$/).test(text)) return null;
    const negative = text.startsWith("-");
    const [rubles, cents = ""] = text.replace(/^-/, "").split(".");
    const result = BigInt(rubles) * 100n + BigInt(cents.padEnd(2, "0"));
    return result <= maxMoney ? (negative ? -result : result) : null;
  };
  const formatMoney = (value) => {
    const absolute = value < 0n ? -value : value;
    return `${value < 0n ? "-" : ""}${absolute / 100n}.${String(absolute % 100n).padStart(2, "0")}`;
  };
  const parseSupplierPrice = (value) => {
    const text = String(value).trim().replace(',', '.');
    if (text.length > 32) return null;
    if (!/^\d+(?:\.\d{1,6})?$/.test(text)) return null;
    const [whole, fraction = ''] = text.split('.');
    const result = BigInt(whole) * 1000000n + BigInt(fraction.padEnd(6, '0'));
    return result > 0n && result <= maxMoney ? result : null;
  };
  // AED и оба курса — миллионные доли. USDT не округляется;
  // ROUND_HALF_UP выполняется ровно один раз на границе копейки RUB.
  const supplierBase = (aed, row) => {
    const price = parseSupplierPrice(aed);
    const ua = parseSupplierPrice(row.dataset.usdtAed), ur = parseSupplierPrice(row.dataset.usdtRub);
    const rate = parseSupplierPrice(row.dataset.aedRub);
    if (price === null) return null;
    const denominator = ua !== null && ur !== null ? ua * 1000000n : 1000000000000n;
    if (!(ua !== null && ur !== null) && rate === null) return null;
    const numerator = price * (ua !== null && ur !== null ? ur : rate) * 100n;
    const result = (numerator + denominator / 2n) / denominator;
    return result <= maxMoney ? result : null;
  };
  const postpaymentFor = (value, surcharge = null) => value + (surcharge ?? (value < 200000n ? 6000n : (value < 300000n ? 8000n : 10000n)));
  const roundCustomerPrice = (value) => ((value + 999n) / 1000n) * 1000n;
  const prepaymentFor = (value, surcharge = null) => {
    if (surcharge !== null) return value >= surcharge ? value - surcharge : null;
    for (const surcharge of [6000n, 8000n, 10000n]) {
      const candidate = value - surcharge;
      if (candidate >= 0n && postpaymentFor(candidate) === value) return candidate;
    }
    for (const candidate of [199999n, 299999n]) {
      const originalPost = postpaymentFor(candidate);
      if (originalPost <= value && roundCustomerPrice(originalPost) === roundCustomerPrice(value)) return candidate;
    }
    return null;
  };
  document.querySelectorAll("[data-procurement-row]").forEach((row) => {
    const markup = row.querySelector("[data-markup]");
    const delivery = row.querySelector("[data-delivery]");
    const prepayment = row.querySelector("[data-prepayment]");
    const postpayment = row.querySelector("[data-postpayment]");
    const surcharge = row.querySelector("[data-postpayment-surcharge]");
    const source = row.querySelector("[data-price-source]");
    const error = row.querySelector("[data-price-error]");
    if (!markup || !delivery || !prepayment || !postpayment || !surcharge || !source) return;
    const highlight = () => {
      const value = parseMoney(markup.value, true);
      const nonpositive = value !== null && value <= 0n;
      markup.classList.toggle("danger-text", nonpositive);
      markup.parentElement.classList.toggle("field-error", nonpositive);
    };
    highlight();
    const fields = [markup, delivery, prepayment, postpayment, surcharge];
    const recalculate = (changed) => {
      fields.forEach((field) => field.setCustomValidity(""));
      if (error) error.textContent = "";
      if (changed === surcharge) row.dataset.surchargeMode = "fixed";
      source.value = changed === prepayment ? "prepayment" : (changed === postpayment ? "postpayment" : "markup");
      const fail = (field, message) => {
        field.setCustomValidity(message);
        if (error) error.textContent = message;
      };
      const base = parseMoney(row.dataset.base);
      const shipping = parseMoney(delivery.value);
      const totalCost = row.querySelector('[data-total-cost-display]');
      if (totalCost) totalCost.textContent = base !== null && shipping !== null ? formatMoney(base + shipping) : '—';
      const fixedSurcharge = row.dataset.surchargeMode === "tiered" ? null : parseMoney(surcharge.value);
      if (base === null) return fail(changed, "Не удалось прочитать базовую цену. Обновите страницу.");
      if (shipping === null) return fail(delivery, "Укажите доставку от 0 с точностью до копеек.");
      if (fixedSurcharge === null && row.dataset.surchargeMode !== "tiered") {
        return fail(surcharge, "Укажите доплату от 0 с точностью до копеек.");
      }
      let prepaid;
      if (source.value === "markup") {
        const margin = parseMoney(markup.value, true);
        highlight();
        if (margin === null) return fail(markup, "Укажите наценку с точностью до копеек.");
        prepaid = base + shipping + margin;
      } else {
        const entered = parseMoney(changed.value);
        if (entered === null) return fail(changed, "Укажите цену от 0 с точностью до копеек.");
        prepaid = source.value === "prepayment" ? entered : prepaymentFor(entered, fixedSurcharge);
        if (prepaid === null) return fail(postpayment,
          fixedSurcharge === null ? "Постоплата: от 60 до 2059,99 ₽, от 2080 до 3079,99 ₽ или от 3100 ₽ по текущему правилу." : "Постоплата не может быть меньше доплаты.");
      }
      const margin = prepaid - base - shipping;
      if (prepaid < 0n) return fail(changed, "Цена предоплаты не может быть отрицательной.");
      const originalPost = postpaymentFor(prepaid, fixedSurcharge);
      const roundedPrepaid = roundCustomerPrice(prepaid);
      const postpaid = roundCustomerPrice(originalPost);
      if (roundedPrepaid > maxMoney || postpaid > maxMoney || margin > maxMoney || margin < -maxMoney) {
        return fail(changed, "Цена превышает допустимую сумму.");
      }
      // Введённое поле не форматируем заново, чтобы не перемещать курсор при наборе.
      if (changed !== markup) markup.value = formatMoney(margin);
      if (changed !== prepayment) prepayment.value = formatMoney(roundedPrepaid);
      if (changed !== postpayment) postpayment.value = formatMoney(postpaid);
      if (changed !== surcharge) surcharge.value = formatMoney(originalPost - prepaid);
      const effective = row.querySelector('[data-effective-markup]');
      if (effective) effective.textContent = formatMoney(roundedPrepaid - base - shipping);
      highlight();
    };
    fields.forEach((field) => field.addEventListener("input", () => {
      if (!field.readOnly) recalculate(field);
    }));
    const supplier = row.querySelector('[data-supplier-select]');
    const manualToggle = row.querySelector('[data-manual-price-toggle]');
    const manualInput = row.querySelector('[data-manual-price]');
    const manualField = row.querySelector('[data-manual-price-field]');
    const manualDrafts = {};
    if (manualToggle && supplier) {
      for (const option of supplier.options) {
        if (option.dataset.canOverride === 'true') manualDrafts[option.value] = {
          enabled: option.dataset.manualActive === 'true', price_aed: option.dataset.manualAed,
        };
      }
    }
    const highlightSupplierOffers = () => {
      const offers = Array.from(row.querySelectorAll('[data-supplier-offer]'));
      const selectedOffer = offers.find((offer) => supplier
        ? offer.dataset.supplierId === supplier.value : offer.getAttribute('aria-current') === 'true');
      const selectedPrice = parseSupplierPrice(selectedOffer?.dataset.priceAed);
      offers.forEach((offer) => {
        const price = parseSupplierPrice(offer.dataset.priceAed);
        offer.classList.toggle('is-expensive', row.dataset.productKind === 'cd' && offer !== selectedOffer
          && price !== null && selectedPrice !== null && price - selectedPrice >= 5000000n);
      });
    };
    highlightSupplierOffers();
    const selectOffer = () => row.querySelectorAll('[data-supplier-offer]').forEach((offer) => {
      const selected = offer.dataset.supplierId === supplier.value;
      offer.classList.toggle('is-selected', selected);
      offer.setAttribute('aria-current', String(selected));
    });
    const updateManualOffers = () => {
      row.querySelectorAll('[data-supplier-offer]').forEach(offer => {
        const draft = manualDrafts[offer.dataset.supplierId];
        const manual = !!draft?.enabled;
        const aed = manual ? draft.price_aed : offer.dataset.originalPriceAed;
        offer.dataset.priceAed = aed;
        if (offer.dataset.supplierLetter !== undefined) {
          const price = parseSupplierPrice(aed);
          const label = price === null ? '—' : `${price / 1000000n}${price % 1000000n ? '.' + String(price % 1000000n).padStart(6, '0').replace(/0+$/, '') : ''}`;
          offer.textContent = `${offer.dataset.supplierLetter}–${label}${manual ? ' ✎' : ''}`;
          offer.title = `${manual ? 'Ручная цена. Исходное предложение: ' + offer.dataset.originalPriceAed + ' AED' : ''}${offer.classList.contains('is-excluded') ? ' · Поставщик исключён из подбора товара' : ''}`;
        }
      });
      highlightSupplierOffers();
    };
    const showManual = () => {
      if (!manualToggle) return;
      const draft = manualDrafts[supplier.value];
      manualToggle.disabled = supplier.disabled || !draft;
      manualToggle.checked = !!draft?.enabled;
      manualField.hidden = !manualToggle.checked;
      manualInput.disabled = supplier.disabled || !manualToggle.checked;
      manualInput.value = draft?.price_aed ?? '';
      manualInput.setCustomValidity('');
    };
    const applyManual = () => {
      if (supplier.disabled) return;
      const draft = manualDrafts[supplier.value];
      const option = supplier.selectedOptions[0];
      const base = draft?.enabled ? supplierBase(draft.price_aed, row) : supplierBase(option?.dataset.originalAed, row);
      manualInput.setCustomValidity('');
      if (base === null) {
        const message = 'Моя цена AED: укажите число больше нуля, до 6 знаков после запятой и в пределах допустимой суммы.';
        manualInput.setCustomValidity(message);
        if (error) error.textContent = message;
        return false;
      }
      row.dataset.base = formatMoney(base);
      recalculate(markup);
      updateManualOffers();
      return true;
    };
    if (manualToggle && supplier) {
      showManual();
      manualToggle.addEventListener('change', () => {
        if (manualToggle.disabled) return;
        manualDrafts[supplier.value].enabled = manualToggle.checked;
        showManual();applyManual();
      });
      manualInput.addEventListener('input', () => {
        if (manualInput.disabled) return;
        manualDrafts[supplier.value].price_aed = manualInput.value;
        applyManual();
      });
      row.manualDrafts = manualDrafts;
      row.validateManualPrices = () => {
        for (const [id, draft] of Object.entries(manualDrafts)) {
          if (draft.enabled && supplierBase(draft.price_aed, row) === null) {
            supplier.value = id;showManual();selectOffer();applyManual();
            manualInput.reportValidity();return false;
          }
        }
        return true;
      };
    }
    supplier?.addEventListener('change', () => {
      if (supplier.disabled) return;
      supplier.setCustomValidity('');
      selectOffer();
      const option = supplier.selectedOptions[0];
      if (manualToggle) {
        showManual();
        if (!applyManual()) return;
      }
      const base = manualToggle ? parseMoney(row.dataset.base) : (option ? parseMoney(option.dataset.base) : null);
      if (base === null) {
        supplier.setCustomValidity('Не удалось прочитать цену поставщика. Обновите страницу.');
        if (error) error.textContent = supplier.validationMessage;
        return;
      }
      // База каждого сохранённого предложения рассчитана сервером в копейках.
      row.dataset.base = formatMoney(base);
      highlightSupplierOffers();
      recalculate(markup);
    });
  });
  document.querySelectorAll(".procurement-pricing-form").forEach((form) => {
    const payload = form.querySelector("[data-pricing-rows]");
    if (!payload) return;
    const confirmed = form.querySelector("[data-negative-confirmed]");
    const dialog = document.querySelector("[data-negative-dialog]");
    const resetConfirmation = () => {
      if (confirmed) { confirmed.value = ""; confirmed.disabled = true; }
    };
    form.addEventListener('input', resetConfirmation);
    form.addEventListener('change', resetConfirmation);
    if (dialog && confirmed) {
      dialog.querySelector("[data-negative-cancel]").addEventListener("click", () => dialog.close());
      dialog.querySelector("[data-negative-accept]").addEventListener("click", () => {
        confirmed.value = "true";
        confirmed.disabled = false;
        dialog.close();
        form.requestSubmit();
      });
    }
    form.addEventListener("submit", (event) => {
      for (const row of form.querySelectorAll('[data-procurement-row]')) {
        if (row.validateManualPrices && !row.validateManualPrices()) { event.preventDefault(); return; }
      }
      const negatives = [...form.querySelectorAll("[data-markup]")].filter(field => {
        const value = parseMoney(field.value, true);
        return value !== null && value < 0n;
      });
      if (negatives.length && confirmed?.value !== "true") {
        event.preventDefault();
        if (dialog && typeof dialog.showModal === "function") {
          dialog.querySelector("[data-negative-count]").textContent = String(negatives.length);
          dialog.showModal();
        } else if (window.confirm(`В ${negatives.length} позициях отрицательная наценка. Вы уверены, что хотите сохранить эти цены?`)) {
          if (confirmed) { confirmed.value = "true"; confirmed.disabled = false; }
          form.requestSubmit();
        }
        return;
      }
      const rows = {};
      form.querySelectorAll("[data-procurement-row]").forEach((row) => {
        rows[row.dataset.itemId] = {
          markup: row.querySelector("[data-markup]").value,
          delivery: row.querySelector("[data-delivery]").value,
          prepayment: row.querySelector("[data-prepayment]").value,
          postpayment: row.querySelector("[data-postpayment]").value,
          price_source: row.querySelector("[data-price-source]").value,
          postpayment_surcharge: row.querySelector("[data-postpayment-surcharge]").value,
          surcharge_mode: row.dataset.surchargeMode,
        };
        const supplier = row.querySelector('[data-supplier-select]');
        if (row.dataset.pricingInitial) rows[row.dataset.itemId].pricing_initial = row.dataset.pricingInitial;
        if (supplier) {
          rows[row.dataset.itemId].supplier_id = supplier.value;
          rows[row.dataset.itemId].supplier_initial_id = supplier.dataset.initialId;
          if (!supplier.disabled && row.manualDrafts && Object.keys(row.manualDrafts).length) rows[row.dataset.itemId].manual_prices = row.manualDrafts;
        }
      });
      // Один параметр формы позволяет сохранять большие прайсы без лимита числа полей.
      payload.value = JSON.stringify(rows);
      payload.disabled = false;
      form.querySelectorAll("[data-procurement-row] input, [data-procurement-row] select").forEach((field) => { field.disabled = true; });
    });
  });
});
