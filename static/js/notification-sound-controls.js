(() => {
  'use strict';
  const button = document.querySelector('[data-notification-sound-enable]');
  if (!button) return;
  const channels = new Map();
  function render() {
    const entries = [...channels.values()];
    const ready = entries.length > 0 && entries.every(entry => entry.state === 'on');
    const busy = entries.some(entry => entry.state === 'loading' || entry.state === 'enabling');
    const blocked = entries.some(entry => entry.state === 'blocked');
    const label = ready ? 'Звуковые уведомления включены' : 'Включить звуковые уведомления';
    button.disabled = ready || busy || !entries.length;
    button.setAttribute('aria-label', label);
    button.setAttribute('aria-pressed', String(ready));
    button.setAttribute('aria-busy', String(busy));
    button.dataset.soundState = blocked ? 'blocked' : ready ? 'on' : busy ? 'enabling' : 'off';
    button.title = [label, ...entries.map(entry => entry.message).filter(Boolean)].join('\n');
  }
  function register(name, enable) {
    const entry = {enable, state: 'loading', message: ''};
    channels.set(name, entry);
    render();
    return (state, message = '') => {
      entry.state = state;
      entry.message = message;
      render();
    };
  }
  button.addEventListener('click', () => {
    if (button.disabled) return;
    // Оба запуска начинаются из одного пользовательского нажатия. Включённые
    // каналы повторно не воспроизводятся: кнопка не служит тестированием звука.
    for (const entry of channels.values()) {
      if (entry.state === 'on') continue;
      entry.state = 'enabling';
      try {
        Promise.resolve(entry.enable()).catch(() => {
          entry.state = 'blocked';
          entry.message = 'Не удалось включить звук. Повторите включение.';
        }).finally(() => {
          if (entry.state === 'enabling') entry.state = 'off';
          render();
        });
      } catch (_) {
        entry.state = 'blocked';
        entry.message = 'Не удалось включить звук. Повторите включение.';
      }
    }
    render();
  });
  window.GameBAT = {...window.GameBAT, notificationSound: {register}};
})();
