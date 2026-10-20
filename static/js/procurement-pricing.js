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
      const roundingPre = row.querySelector('[data-prepayment-rounding]');
      const roundingPost = row.querySelector('[data-postpayment-rounding]');
      if (roundingPre) roundingPre.textContent = formatMoney(roundedPrepaid - prepaid);
      if (roundingPost) roundingPost.textContent = formatMoney(postpaid - originalPost);
      highlight();
    };
    fields.forEach((field) => field.addEventListener("input", () => {
      if (!field.readOnly) recalculate(field);
    }));
  });
  document.querySelectorAll(".procurement-pricing-form").forEach((form) => {
    const payload = form.querySelector("[data-pricing-rows]");
    if (!payload) return;
    const confirmed = form.querySelector("[data-negative-confirmed]");
    const dialog = document.querySelector("[data-negative-dialog]");
    form.addEventListener("input", () => {
      if (confirmed) { confirmed.value = ""; confirmed.disabled = true; }
    });
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
      });
      // Один параметр формы позволяет сохранять большие прайсы без лимита числа полей.
      payload.value = JSON.stringify(rows);
      payload.disabled = false;
      form.querySelectorAll("[data-procurement-row] input").forEach((field) => { field.disabled = true; });
    });
  });
});
