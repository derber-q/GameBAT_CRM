'use strict';
importScripts('protocol.js');
const PREFIX = 'resource-avito:';
const locks = new Map();

async function bridge(state, action, data = {}) {
  let response;
  try {
    const tab = await chrome.tabs.get(state.crmTab);
    if (!ResourceAvito.isCrm(tab.url) || new URL(tab.url).origin !== state.origin) throw new Error();
    response = await chrome.tabs.sendMessage(state.crmTab, {type: PREFIX + 'bridge', action, ...data});
  } catch {
    throw new Error('Оставьте исходную вкладку Avito Check открытой. Если она закрыта, начните ручной поиск из CRM снова.');
  }
  if (!response?.ok) throw new Error(response?.message || 'CRM не ответила. Проверьте подключение и вход в аккаунт.');
  return response;
}

async function start(message, sender) {
  if (!ResourceAvito.isCrm(sender.url)) throw new Error('Начните ручной поиск на странице Avito Check.');
  const state = {crmTab: sender.tab.id, origin: new URL(sender.url).origin};
  const response = await bridge(state, 'queue', {query: String(message.query || ''), sort: message.sort});
  if (!Array.isArray(response.items) || response.items.length > 10000) throw new Error('Некорректная очередь CRM.');
  const seen = new Set();
  state.items = response.items.map(item => {
    if (!Number.isSafeInteger(item.id) || item.id <= 0 || seen.has(item.id) || !ResourceAvito.isAvito(item.search_url)) {
      throw new Error('Некорректный товар в очереди CRM.');
    }
    seen.add(item.id);
    return {id: item.id, search_url: item.search_url};
  });
  state.index = state.items.findIndex(item => item.id === message.productId);
  if (state.index < 0) throw new Error('Товар выбыл из текущего списка. Обновите Avito Check.');
  state.completed = 0;
  const tab = await chrome.tabs.create({url: 'about:blank', active: true});
  const key = String(tab.id);
  try {
    await chrome.storage.session.set({[key]: state});
    await chrome.tabs.update(tab.id, {url: state.items[state.index].search_url});
  } catch (error) {
    await chrome.storage.session.remove(key);
    throw error;
  }
  return {ok: true};
}

async function handle(message, sender) {
  if (sender.id !== chrome.runtime.id || sender.frameId !== 0 || !sender.tab) throw new Error('Недопустимый источник команды.');
  if (message.type === PREFIX + 'start') return start(message, sender);
  if (!ResourceAvito.isAvito(sender.url)) throw new Error('Панель доступна только на Avito.');
  const key = String(sender.tab.id);
  const state = (await chrome.storage.session.get(key))[key];
  if (!state) return {ok: true, inactive: true};
  const progress = {index: state.index + 1, total: state.items.length, completed: state.completed,
    crmUrl: state.origin + '/crm/pricing/avito-check/'};
  if (state.index >= state.items.length) return {ok: true, done: true, ...progress};
  const current = state.items[state.index];
  if (message.type === PREFIX + 'current') {
    const response = await bridge(state, 'product', {productId: current.id});
    if (response.product?.id !== current.id) throw new Error('CRM вернула другой товар. Обновите панель.');
    return {ok: true, product: response.product, ...progress};
  }
  if (message.productId !== current.id) throw new Error('Товар уже изменился. Обновите панель перед сохранением.');
  if (message.type === PREFIX + 'save') {
    const price = ResourceAvito.price(message.price);
    await bridge(state, 'save', {productId: current.id, price, version: String(message.version || '')});
    state.completed += 1;
  } else if (message.type !== PREFIX + 'skip') {
    throw new Error('Неизвестная команда.');
  }
  state.index += 1;
  await chrome.storage.session.set({[key]: state});
  return {ok: true, done: state.index >= state.items.length,
    nextUrl: state.items[state.index]?.search_url, completed: state.completed};
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!['start', 'current', 'save', 'skip'].some(action => message?.type === PREFIX + action)) return false;
  // Команды каждой вкладки последовательны: повторное нажатие не сохраняет следующий товар.
  const key = sender.tab?.id;
  const previous = locks.get(key) || Promise.resolve();
  const task = previous.catch(() => {}).then(() => handle(message, sender));
  locks.set(key, task);
  task.then(sendResponse, error => sendResponse({ok: false, message: error.message || 'Ошибка расширения.'}))
    .finally(() => { if (locks.get(key) === task) locks.delete(key); });
  return true;
});
chrome.tabs.onRemoved.addListener(tabId => { chrome.storage.session.remove(String(tabId)); });
