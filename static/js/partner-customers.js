(() => {
  'use strict';
  document.querySelectorAll('select[name="customer"]').forEach(select => {
    const form = select.form, custom = form.querySelector('[name="custom_partner_name"]');
    const type = form.querySelector('[name="sale_type"]');
    const payment = form.querySelector('[name="payment_method"]');
    const debtOption = payment?.querySelector('option[value="partner_debt"]');
    function sync() {
      const visible = !type || type.value === 'wholesale';
      if (debtOption) {
        const available = visible && !!type && !!select.value && select.value !== 'custom';
        debtOption.hidden = debtOption.disabled = !available;
        if (!available && payment.value === 'partner_debt') {
          payment.value = 'cash';
          payment.dispatchEvent(new Event('change', {bubbles: true}));
        }
      }
      select.closest('.field')?.toggleAttribute('hidden', !visible);
      const fixed = select.hasAttribute('data-fixed-customer');
      select.disabled = !visible || fixed;
      select.required = visible && !!type;
      if (custom) {
        custom.closest('.field')?.toggleAttribute('hidden', !visible || select.value !== 'custom');
        custom.disabled = !visible || select.value !== 'custom' || fixed;
        custom.required = visible && select.value === 'custom';
      }
    }
    if (select.disabled) select.setAttribute('data-fixed-customer', 'true');
    select.addEventListener('change', sync);
    type?.addEventListener('change', sync);
    sync();
  });
})();
