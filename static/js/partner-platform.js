(() => {
  'use strict';
  const checkbox = document.querySelector('[name="create_platform"]');
  if (!checkbox) return;
  const form = checkbox.form;
  const fields = form.querySelector('[data-new-platform]');
  const existing = form.querySelector('[name="platform"]');
  if (!fields || !existing) return;
  function sync() {
    fields.hidden = fields.disabled = !checkbox.checked;
    existing.disabled = checkbox.checked;
    if (checkbox.checked) {
      for (const name of ['name', 'address', 'phone_1', 'phone_2']) {
        const source = form.querySelector(`[name="${name}"]`);
        const target = fields.querySelector(`[name="new_platform-${name}"]`);
        if (source && target && !target.value) target.value = source.value;
      }
    }
  }
  checkbox.addEventListener('change', sync);
  sync();
})();
