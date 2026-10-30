(() => {
  'use strict';
  const root = document.getElementById('market-order-alerts');
  const api = window.GameBAT?.marketAlertState;
  if (!root || !api) return;
  const audioStatus = root.querySelector('[data-market-audio-status]');
  const feedStatus = root.querySelector('[data-market-feed-status]');
  const csrfForm = root.querySelector('[data-market-csrf]');
  const state = new api.IndexedState();
  const owner = `${Date.now()}:${Math.random()}`;
  const audio = new Audio(root.dataset.soundUrl);
  audio.preload = 'auto';
  audio.volume = 1;
  audio.dataset.notificationChannel = 'market';
  let channel;
  try {channel = new BroadcastChannel('gamebat-market-alerts');} catch (_) {channel = null;}
  let orders = [], offset = 0, period = 600000, fresh = false, lastFeed = 0;
  let enabled = false, blocked = false, enabling = false, pumping = false, active = null;
  let generation = 0, flight = null, feedController = null, warning = '';
  const broadcast = (type) => channel?.postMessage({type});
  const serverNow = () => Date.now() + offset;
  const pending = id => orders.some(row => String(row.id) === String(id));
  const reportSound = window.GameBAT.notificationSound.register('market', enableSound);

  function publishSoundState() {
    reportSound(blocked ? 'blocked' : enabling ? 'enabling' : enabled ? 'on' : 'off', audioStatus.textContent);
  }

  function soundMessage(message, error = false) {
    audioStatus.textContent = message;
    audioStatus.classList.toggle('error-text', error);
    publishSoundState();
  }
  function soundError(error) {
    blocked = true;
    soundMessage(error?.name === 'NotAllowedError'
      ? 'Браузер заблокировал звук. Нажмите «Включить звуковые уведомления».'
      : 'Звук не воспроизводится. Проверьте звук браузера и повторите включение.', true);
  }
  function stopActive() {
    if (active) active.cancelled = true;
    audio.pause();
    active?.cancel();
  }
  function unavailable(error) {
    fresh = false;
    stopActive();
    const message = 'Нет актуальных уведомлений: проверьте сеть и вход в CRM. Повторяем соединение; звук приостановлен.';
    feedStatus.textContent = message;
    feedStatus.classList.add('error-text');
    if (warning !== message) console.warn('Уведомления Маркета: ошибка синхронизации', error?.name || 'Error');
    warning = message;
  }
  function makeCard(order, allowed) {
    const card = document.createElement('li');
    card.className = 'panel market-attention-card market-order-unacknowledged';
    card.dataset.marketAttention = order.id;
    const label = document.createElement('strong');
    label.textContent = `Заказ Яндекса №${order.order_id}`;
    card.append(label);
    if (order.detail_url) {
      const link = document.createElement('a');
      link.href = order.detail_url; link.textContent = 'Открыть продажу'; card.append(link);
    }
    if (allowed && order.ack_url) {
      const form = document.createElement('form');
      form.method = 'post'; form.action = order.ack_url; form.dataset.marketAck = '';
      const accept = document.createElement('button');
      accept.type = 'submit'; accept.className = 'button'; accept.textContent = 'Заказ принят';
      form.append(accept); card.append(form);
    }
    return card;
  }
  function apply(snapshot) {
    if (!Array.isArray(snapshot.orders) || !Number.isFinite(Date.parse(snapshot.server_now))
        || snapshot.count !== snapshot.orders.length) throw new Error('Некорректный ответ уведомлений.');
    orders = snapshot.orders;
    offset = Date.parse(snapshot.server_now) - Date.now();
    period = snapshot.repeat_seconds * 1000;
    if (period !== 600000) throw new Error('Некорректный интервал уведомлений.');
    fresh = true; lastFeed = Date.now(); warning = '';
    feedStatus.textContent = ''; feedStatus.classList.remove('error-text');
    document.querySelectorAll('[data-market-pending-count]').forEach(node => {node.textContent = snapshot.count;});
    document.querySelectorAll('[data-market-counter]').forEach(node => {
      node.classList.toggle('has-pending', snapshot.count > 0);
      const label = `Яндекс Маркет: непринятых заказов — ${snapshot.count}`;
      node.setAttribute('aria-label', label);
      node.title = label;
    });
    const list = document.querySelector('[data-market-attention-list]');
    document.querySelectorAll('[data-market-attention]').forEach(node => {
      const required = pending(node.dataset.marketAttention);
      node.classList.toggle('market-order-unacknowledged', required && node.matches('tr, li'));
      node.querySelectorAll('[data-market-ack], [data-market-new-badge]').forEach(control => {control.hidden = !required;});
      if (!required && list?.contains(node)) node.remove();
    });
    if (list) {
      orders.forEach(order => {
        if (!list.querySelector(`[data-market-attention="${order.id}"]`)) list.append(makeCard(order, snapshot.can_acknowledge));
      });
      const empty = document.querySelector('[data-market-pending-empty]');
      if (empty) empty.hidden = orders.length > 0;
    }
    if (active?.lease.orderId != null && !pending(active.lease.orderId)) stopActive();
    void pump();
  }
  async function jsonRequest(url, options = {}) {
    const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store',
      ...options, headers: {Accept: 'application/json'}});
    if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Проверьте вход в CRM.');
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Не удалось обновить уведомления.');
    return result;
  }
  function refresh() {
    if (flight) return flight;
    const version = ++generation;
    feedController = new AbortController();
    const controller = feedController;
    const timeout = setTimeout(() => controller.abort(), 10000);
    flight = jsonRequest(root.dataset.feedUrl, {signal: controller.signal}).then(snapshot => {
      if (version === generation) apply(snapshot);
      return version === generation;
    }).catch(error => {
      if (version === generation) unavailable(error);
      return false;
    }).finally(() => {
      clearTimeout(timeout);
      if (version === generation) flight = null;
    });
    return flight;
  }
  async function play(lease, test = false) {
    let heartbeat, timeout;
    let finish;
    const ended = new Promise((resolve, reject) => {
      finish = resolve;
      audio.onended = resolve;
      audio.onerror = () => reject(new Error('Не удалось загрузить звук.'));
    });
    // Обработчик устанавливается сразу, в том числе на отказ запуска play().
    ended.catch(() => {});
    const playback = {lease, cancel: finish, cancelled: false};
    active = playback;
    audio.volume = 1; audio.currentTime = 0;
    audio.dataset.marketOrderId = lease.orderId === null ? 'test' : String(lease.orderId);
    heartbeat = setInterval(() => {
      state.renew(lease).then(ours => {if (!ours) stopActive();}).catch(error => {stopActive(); soundError(error);});
    }, 5000);
    try {
      await Promise.race([audio.play(), new Promise((resolve, reject) => {
        timeout = setTimeout(() => reject(new Error('Истекло время запуска звука.')), 10000);
      })]);
      clearTimeout(timeout);
      if (playback.cancelled) return;
      if (!await state.started(lease)) throw new Error('Звуковой исполнитель сменился.');
      if (test) {
        await state.enable(); enabled = true; blocked = false;
        soundMessage('Звук включён для уведомлений Яндекс Маркета.');
        broadcast('enabled');
      } else {
        soundMessage(`Сигнал: заказ Яндекса №${orders.find(row => String(row.id) === String(lease.orderId))?.order_id || ''}`);
      }
      await Promise.race([ended, new Promise((resolve, reject) => {
        timeout = setTimeout(() => reject(new Error('Воспроизведение не завершилось.')), 45000);
      })]);
    } catch (error) {
      if (!playback.cancelled) throw error;
    } finally {
      clearInterval(heartbeat); clearTimeout(timeout);
      audio.pause(); audio.onended = null; audio.onerror = null;
      active = null;
      await state.release(lease);
      broadcast('speaker-free');
    }
  }
  async function pump() {
    if (pumping || active || !enabled || blocked || !fresh || !orders.length) return;
    if (Date.now() - lastFeed > 45000) {void refresh(); return;}
    pumping = true;
    try {
      while (fresh && enabled && !blocked) {
        const lease = await state.claim(orders, serverNow(), owner, period);
        if (!lease) break;
        if (!await refresh() || !pending(lease.orderId)) {
          await state.release(lease);
          if (!fresh) break;
          continue;
        }
        await play(lease);
      }
    } catch (error) {soundError(error);}
    finally {pumping = false;}
  }
  async function enableSound() {
    if (active || enabling) return;
    enabling = true;
    publishSoundState();
    try {
      const lease = await state.claim([], serverNow(), owner, period, true);
      if (!lease) {soundMessage('Сигнал уже выполняется в другой вкладке. Повторите включение после него.'); return;}
      await play(lease, true);
      void refresh();
      void pump();
    } catch (error) {soundError(error);}
    finally {enabling = false; publishSoundState();}
  }
  document.addEventListener('submit', async event => {
    const form = event.target.closest('[data-market-ack]');
    if (!form) return;
    event.preventDefault();
    const accept = form.querySelector('button');
    if (accept.disabled) return;
    accept.disabled = true;
    const errorNode = document.querySelector('[data-market-ack-error]') || feedStatus;
    errorNode.textContent = '';
    const data = new FormData(csrfForm);
    ++generation; feedController?.abort(); flight = null;
    try {
      const snapshot = await jsonRequest(form.action, {method: 'POST', body: data});
      apply(snapshot); broadcast('acknowledged');
    } catch (error) {
      errorNode.textContent = error.message;
      errorNode.classList.add('error-text');
      void refresh();
    } finally {accept.disabled = false;}
  });
  channel?.addEventListener('message', event => {
    if (event.data?.type === 'acknowledged') void refresh();
    else if (event.data?.type === 'enabled') {enabled = true; publishSoundState(); void pump();}
    else if (event.data?.type === 'speaker-free') void pump();
  });
  function resume() {void refresh();}
  window.addEventListener('online', resume);
  window.addEventListener('focus', resume);
  document.addEventListener('visibilitychange', () => {if (!document.hidden) resume();});
  window.addEventListener('pagehide', () => {
    if (active) {stopActive(); void state.release(active.lease).catch(() => {});}
  });
  state.enabled().then(value => {
    enabled = value;
    if (enabled) soundMessage('Звук Яндекс Маркета включён; при блокировке браузера потребуется повторное включение.');
    else publishSoundState();
    void pump();
  }).catch(error => {soundError(error);});
  setInterval(() => {
    void refresh();
    if (!enabled) state.enabled().then(value => {enabled = value; publishSoundState(); void pump();}).catch(() => {});
  }, 15000);
  setInterval(() => {void pump();}, 1000);
  window.GameBAT = {...window.GameBAT, refreshMarketNotifications: refresh};
  void refresh();
})();
