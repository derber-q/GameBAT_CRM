/* Локальный статус и отдельный звуковой канал. GET не запускает обработчики. */
(() => {
  'use strict';
  const root = document.querySelector('[data-worker-monitor]');
  if (!root) return;
  const icon = document.querySelector('[data-worker-alert]');
  const audioStatus = root.querySelector('[data-worker-audio-status]');
  const feedStatus = root.querySelector('[data-worker-feed-status]');
  const state = new window.GameBAT.marketAlertState.IndexedState(undefined, `gamebat-worker-alerts-${root.dataset.user}`);
  const audio = new Audio(root.dataset.soundUrl);
  audio.dataset.notificationChannel = 'workers';
  const owner = `${Date.now()}:${Math.random()}`;
  const period = 600000;
  let enabled = false, blocked = false, fresh = false, pumping = false, stopped = false;
  let incidents = [], offset = 0, timer, flight, controller, lastFeed = 0, cancelAudio;
  const now = () => Date.now() + offset;
  const report = window.GameBAT.notificationSound.register('workers', enableSound);
  const text = (selector, value) => { const node = document.querySelector(selector); if (node) node.textContent = value; };
  const date = (value, fallback = 'Нет данных') => value && Number.isFinite(Date.parse(value))
    ? new Date(value).toLocaleString('ru-RU', {timeZone: 'Europe/Moscow'}) : fallback;
  function soundState() { report(blocked ? 'blocked' : enabled ? 'on' : 'off', audioStatus.textContent); }
  function stopAudio() { audio.pause(); cancelAudio?.(); }
  function soundFailed() {
    blocked = true;
    audioStatus.textContent = 'Обработчики: звук недоступен. Нажмите общий значок звука и проверьте разрешение браузера.';
    soundState();
  }
  async function play(lease) {
    let timeout;
    try {
      audio.currentTime = 0;
      await new Promise((resolve, reject) => {
        cancelAudio = resolve;
        audio.onended = resolve;
        audio.onerror = () => reject(new Error('Audio unavailable'));
        timeout = setTimeout(() => reject(new Error('Audio timeout')), 45000);
        audio.play().then(async () => {
          try { await state.started(lease); } catch (error) { reject(error); }
        }, reject);
      });
    } finally {
      clearTimeout(timeout); audio.pause(); audio.onended = audio.onerror = null; cancelAudio = null;
    }
  }
  async function pump(test = false) {
    if (pumping || (!test && (!enabled || blocked || !fresh || Date.now() - lastFeed > 30000))) return;
    pumping = true;
    let lease;
    try {
      lease = await state.claim(incidents, now(), owner, period, test && !incidents.length);
      if (lease && (test || fresh)) await play(lease);
    } catch (_) { soundFailed(); }
    finally { if (lease) await state.release(lease).catch(() => {}); pumping = false; }
  }
  async function enableSound() {
    // play вызывается в той же цепочке пользовательского действия; браузер
    // вправе отказать, тогда визуальный сигнал продолжает работать.
    blocked = false;
    await pump(true);
    if (!blocked) {
      await state.enable(); enabled = true;
      audioStatus.textContent = 'Звук предупреждений об обработчиках включён.';
      soundState();
    }
  }
  function unavailable() {
    fresh = false; incidents = []; stopAudio();
    if (icon) { icon.hidden = false; icon.title = 'Состояние обработчиков неизвестно: нет актуальных данных'; icon.setAttribute('aria-label', icon.title); }
    feedStatus.textContent = 'Нет актуальных данных об обработчиках. Проверьте сеть и вход в CRM.';
    text('[data-worker-summary]', feedStatus.textContent);
    for (const button of document.querySelectorAll('[data-worker-command] button')) button.disabled = true;
  }
  function render(data) {
    const previousIds = new Set(incidents.map(item => item.id));
    incidents = data.incidents;
    if (!data.alarm || [...previousIds].some(id => !incidents.some(item => item.id === id))) stopAudio();
    fresh = true; lastFeed = Date.now(); offset = Date.parse(data.server_time) - Date.now();
    if (icon) { icon.hidden = !data.alarm; icon.title = data.controller_alarm ? 'Контроллер недоступен' : 'Проблема обработчиков'; icon.setAttribute('aria-label', icon.title); }
    feedStatus.textContent = '';
    text('[data-worker-summary]', data.controller_label + (data.alarm ? ' · Требуется внимание' : data.mode === 'managed' ? ' · Все необходимые обработчики работают' : ''));
    text('[data-worker-counts]', `Работают: ${data.running_count} · Требуют внимания: ${data.stopped_count} · Отключены или не настроены: ${data.disabled_count}`);
    text('[data-worker-observed]', date(data.observed_at));
    for (const agent of data.print_agents || []) {
      const node = document.querySelector(`[data-print-agent="${agent.id}"]`);
      if (!node) continue;
      for (const field of node.querySelectorAll('[data-agent-field]')) {
        const key = field.dataset.agentField;
        let value = agent[key];
        if (key === 'connected') value = value ? 'Подключён' : 'Нет связи';
        if (key === 'printer_available') value = value == null ? 'Нет данных' : value ? 'Да' : 'Нет';
        if (key === 'last_seen_at') value = date(value);
        field.textContent = value ?? '';
      }
    }
    for (const row of data.services) {
      const node = document.querySelector(`[data-worker-row="${row.code}"]`);
      if (!node) continue;
      node.dataset.alarm = String(row.alarm);
      for (const field of node.querySelectorAll('[data-field]')) {
        const key = field.dataset.field;
        let value = row[key];
        if (key.endsWith('_at')) value = date(value, key === 'next_at' ? (row.code === 'print' ? 'По поступлению' : 'Не запланировано') : 'Нет данных');
        if (key === 'next_at' && row.overdue) value = `Просрочено с ${value}`;
        if (key === 'failures') value = `${value} / 3`;
        if (key === 'paused') value = value ? 'Приостановлено' : 'Разрешено для необходимых обработчиков';
        field.textContent = value ?? '';
      }
      const button = node.querySelector('[data-worker-command] button');
      if (button) button.disabled = !row.can_start || data.commands?.some(command => command.service === row.code && ['queued', 'running'].includes(command.state));
    }
    const restore = document.querySelector('.worker-summary [data-worker-command] button');
    if (restore) restore.disabled = !data.services.some(row => row.can_start);
    if (data.commands?.length) {
      const names = Object.fromEntries(data.services.map(row => [row.code, row.name]));
      const seen = new Set();
      text('[data-worker-command-result]', data.commands.filter(command => {
        if (seen.has(command.service)) return false; seen.add(command.service); return true;
      }).map(command => `${names[command.service]}: ${command.label}${command.result ? ` — ${command.result}` : ''}`).join(' · '));
    }
    const history = document.querySelector('[data-worker-history]');
    if (history && data.history) {
      history.replaceChildren();
      for (const item of data.history) {
        const tr = document.createElement('tr');
        for (const value of [date(item.created_at), item.service, item.kind, item.result, item.actor]) {
          const td = document.createElement('td'); td.textContent = value; tr.append(td);
        }
        history.append(tr);
      }
    }
    state.enabled().then(value => { enabled = value; soundState(); pump(); }).catch(soundFailed);
  }
  async function poll() {
    if (flight || stopped) return flight;
    clearTimeout(timer);
    controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    flight = (async () => {
      try {
        const response = await fetch(root.dataset.statusUrl, {credentials: 'same-origin', cache: 'no-store', signal: controller.signal});
        if (!response.ok || response.redirected) throw new Error('Status unavailable');
        const data = await response.json();
        if (!Array.isArray(data.services) || !Array.isArray(data.incidents) || !Number.isFinite(Date.parse(data.server_time))) throw new Error('Invalid status');
        if (!stopped) render(data);
      } catch (_) { if (!stopped) unavailable(); }
      finally { clearTimeout(timeout); flight = null; if (!stopped) timer = setTimeout(poll, 15000); }
    })();
    return flight;
  }
  document.querySelector('[data-worker-refresh]')?.addEventListener('click', poll);
  for (const form of document.querySelectorAll('[data-worker-command]')) form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button');
    if (button.disabled) return;
    button.disabled = true;
    form.dataset.requestId ||= crypto.randomUUID?.() || 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
      const r = Math.floor(Math.random() * 16); return (c === 'x' ? r : (r & 3) | 8).toString(16);
    });
    const body = new FormData(form); body.set('request_id', form.dataset.requestId);
    try {
      const response = await fetch(form.action, {method: 'POST', credentials: 'same-origin', body});
      if (!response.ok || response.redirected) throw new Error('Command failed');
      const data = await response.json(); text('[data-worker-command-result]', data.message);
      delete form.dataset.requestId;
    } catch (_) { text('[data-worker-command-result]', 'Не удалось подтвердить приём команды. Повторите запрос; он защищён от дублирования.'); }
    finally { await poll(); }
  });
  state.enabled().then(value => { enabled = value; soundState(); pump(); }).catch(soundFailed);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
  window.addEventListener('pagehide', () => { stopped = true; clearTimeout(timer); controller?.abort(); stopAudio(); });
  window.addEventListener('pageshow', () => { if (stopped) { stopped = false; poll(); } });
  poll();
})();
