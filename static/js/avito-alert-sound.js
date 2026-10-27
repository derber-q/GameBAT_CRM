(() => {
  'use strict';
  const root = document.querySelector('[data-avito-sound]');
  if (!root) return;
  const button = root.querySelector('[data-avito-sound-enable]');
  const status = root.querySelector('[data-avito-sound-status]');
  let audio, fallbackState;
  const enabledKey = 'resource.avito.sound.v1', stateKey = 'resource.avito.actions.v1';
  let blocked = false, latest = null;
  function read(key) {const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : null;}
  function save(value) {localStorage.setItem(stateKey, JSON.stringify(value));}
  async function play() {
    if (!audio) {audio = new Audio(root.dataset.soundUrl); audio.volume = 1;}
    let timer;
    try {
      audio.currentTime = 0;
      await new Promise((resolve, reject) => {
        audio.onended = resolve;
        audio.onerror = () => reject(new Error('Не удалось загрузить звук Avito.'));
        timer = setTimeout(() => reject(new Error('Звук Avito не завершился.')), 45000);
        audio.play().catch(reject);
      });
    } finally {clearTimeout(timer); audio.pause(); audio.onended = audio.onerror = null;}
  }
  function failed() {
    blocked = true;
    button.textContent = 'Включить звук Avito';
    status.textContent = 'Разрешите звук: нажмите «Включить звук Avito» и проверьте громкость браузера.';
    status.classList.add('error-text');
  }
  async function locked(callback) {
    if (navigator.locks) return navigator.locks.request('resource-avito-sound', callback);
    // На локальном HTTP-адресе Web Locks недоступен; IndexedDB также согласует вкладки.
    fallbackState ||= new window.GameBAT.marketAlertState.IndexedState();
    const token = `${Date.now()}:${Math.random()}`, deadline = Date.now() + 65000;
    let acquired = false;
    while (!acquired && Date.now() < deadline) {
      acquired = await fallbackState.run((values, store) => {
        if ((values.get('avito-speaker')?.expires || 0) > Date.now()) return false;
        store.put({key: 'avito-speaker', token, expires: Date.now() + 60000});
        return true;
      });
      if (!acquired) await new Promise(resolve => setTimeout(resolve, 100));
    }
    if (!acquired) throw new Error('Звук Avito занят другой вкладкой.');
    try {return await callback();}
    finally {
      await fallbackState.run((values, store) => {
        if (values.get('avito-speaker')?.token === token) store.delete('avito-speaker');
      });
    }
  }
  async function observe(snapshot) {
    if (!Array.isArray(snapshot.action_keys) || !snapshot.action_keys.every(key => typeof key === 'string')
        || snapshot.action_keys.length !== snapshot.count || !Number.isFinite(Date.parse(snapshot.observed_at))) return;
    latest = {keys: snapshot.action_keys, at: Date.parse(snapshot.observed_at)};
    try {
      await locked(async () => {
        const previous = read(stateKey), current = latest;
        if (previous && previous.at > current.at) return;
        const added = previous && current.keys.some(key => !previous.keys.includes(key));
        if (added && read(enabledKey) && !blocked) {
          await play();
          status.textContent = 'Avito: появились новые необходимые действия.';
        }
        save(current);
      });
    } catch (_) {failed();}
  }
  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      // Запуск именно из нажатия разрешает звук в браузере.
      await play();
      await locked(() => {
        localStorage.setItem(enabledKey, 'true');
        const previous = read(stateKey);
        if (latest && (!previous || latest.at >= previous.at)) save(latest);
      });
      blocked = false;
      button.textContent = 'Проверить звук Avito';
      status.classList.remove('error-text');
      status.textContent = 'Звук Avito включён. Новые действия будут озвучены автоматически.';
    } catch (_) {failed();}
    finally {button.disabled = false;}
  });
  try {if (read(enabledKey)) button.textContent = 'Проверить звук Avito';} catch (_) {failed();}
  window.GameBAT = {...window.GameBAT, avitoAlertSound: {observe}};
})();
