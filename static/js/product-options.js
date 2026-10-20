document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-newness-options]').forEach((block) => {
    const choice = block.querySelector('[data-newness-duration]');
    const custom = block.querySelector('[data-newness-custom]');
    const wrap = block.querySelector('[data-newness-custom-wrap]');
    if (!choice || !custom || !wrap) return;
    const update = () => {
      const selected = choice.value === 'custom';
      wrap.hidden = !selected;
      custom.required = selected && !choice.disabled;
      custom.disabled = choice.disabled || !selected;
    };
    choice.addEventListener('change', update);
    update();
  });
});
