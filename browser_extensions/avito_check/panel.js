(() => {
  'use strict';
  const prefix = 'resource-avito:';
  let product;
  let busy = false;
  let host;
  let root;
  let title;
  let progress;
  let input;
  let status;
  let form;
  let controls;
  const picker = ResourceAvitoCards.pricePicker(value => {
    if (busy || !product || form.hidden) return false;
    input.value = value;
    picker.setMinimum(input.value);
    showStatus(`Выбрана цена без скидки: ${value} ₽. Нажмите «Сохранить и следующий».`, true);
    input.focus({preventScroll: true});
    return true;
  }, message => { if (!busy) showStatus(message); });

  function showStatus(message, info = false) {
    status.textContent = message;
    status.dataset.kind = info ? 'info' : 'error';
  }

  async function send(action, data = {}) {
    let result;
    try { result = await chrome.runtime.sendMessage({type: prefix + action, ...data}); }
    catch { throw new Error('Расширение обновлено или отключено. Обновите вкладку и начните поиск из CRM снова.'); }
    if (!result?.ok) throw new Error(result?.message || 'Нет ответа от CRM.');
    return result;
  }
  function element(tag, text, parent) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (parent) parent.append(node);
    return node;
  }
  function build() {
    if (host) return;
    host = element('resource-avito-check');
    host.dataset.version = chrome.runtime.getManifest().version;
    document.documentElement.append(host);
    root = host.attachShadow({mode: 'open'});
    element('style', `
      :host{all:initial;position:fixed;top:16px;right:16px;z-index:2147483647;width:330px;max-width:calc(100vw - 32px);color:#24384a;font:14px/1.45 Arial,sans-serif;color-scheme:light}
      *{box-sizing:border-box}section{background:white;border:1px solid #bbd7de;border-radius:12px;box-shadow:0 8px 36px #162c3c40;overflow:hidden}
      header{display:flex;align-items:center;justify-content:space-between;background:#eaf5f7;padding:10px 14px;font-weight:bold}
      .body{padding:14px}h2{font-size:15px;line-height:1.4;margin:0 0 6px;overflow-wrap:anywhere}p{margin:0 0 12px}.progress{color:#596c7a;font-size:12px}
      label{display:block;font-weight:bold;margin-bottom:5px}input{font:inherit;width:100%;padding:10px;border:1px solid #8ea4b0;border-radius:6px;margin-bottom:10px}
      button{font:inherit;cursor:pointer;border:1px solid #b7cad2;border-radius:6px;padding:9px 11px;background:#fff;color:#24384a}
      button:disabled{cursor:wait;opacity:.65}.primary{width:100%;color:#fff;background:#237e90;border-color:#237e90;font-weight:bold}
      .actions{display:flex;gap:8px;margin-top:8px}.actions button{flex:1;padding:7px;font-size:12px}.toggle{border:0;background:none;padding:0 4px;font-size:20px}
      :focus-visible{outline:3px solid #1384c4;outline-offset:2px}.version{font-size:11px;color:#596c7a;margin-left:auto;margin-right:10px}.status{color:#ac243f;margin:10px 0 0;font-size:13px;overflow-wrap:anywhere}.status[data-kind="info"]{color:#286743}.status:empty{display:none}[hidden]{display:none!important}
    `, root);
    const section = element('section', '', root);
    const header = element('header', '', section);
    element('span', 'ReSOURCE · Avito Check', header);
    element('small', host.dataset.version, header).className = 'version';
    const toggle = element('button', '−', header);
    toggle.className = 'toggle';
    toggle.setAttribute('aria-label', 'Свернуть панель');
    toggle.setAttribute('aria-expanded', 'true');
    const body = element('div', '', section);
    body.className = 'body';
    toggle.addEventListener('click', () => {
      body.hidden = !body.hidden;
      toggle.textContent = body.hidden ? '+' : '−';
      toggle.setAttribute('aria-expanded', String(!body.hidden));
      toggle.setAttribute('aria-label', body.hidden ? 'Развернуть панель' : 'Свернуть панель');
    });
    title = element('h2', 'Загрузка товара…', body);
    progress = element('p', '', body);
    progress.className = 'progress';
    form = element('form', '', body);
    const label = element('label', 'Минимальная цена, ₽', form);
    input = element('input', '', form);
    input.id = 'minimum-price';
    input.type = 'text';
    input.inputMode = 'decimal';
    input.maxLength = 25;
    input.required = true;
    input.autocomplete = 'off';
    input.addEventListener('input', () => picker.setMinimum(input.value));
    label.htmlFor = input.id;
    const save = element('button', 'Сохранить и следующий', form);
    save.type = 'submit';
    save.className = 'primary';
    controls = element('div', '', body);
    controls.className = 'actions';
    const skip = element('button', 'Пропустить', controls);
    skip.type = 'button';
    const refresh = element('button', 'Обновить панель', controls);
    refresh.type = 'button';
    status = element('p', '', body);
    status.className = 'status';
    status.setAttribute('role', 'alert');
    form.addEventListener('submit', event => { event.preventDefault(); act('save'); });
    skip.addEventListener('click', () => act('skip'));
    refresh.addEventListener('click', () => load());
  }
  function pending(value) {
    busy = value;
    root.querySelectorAll('input,button:not(.toggle)').forEach(node => { node.disabled = value; });
  }
  function done(completed) {
    picker.setMinimum('');
    title.textContent = 'Проверка списка завершена';
    progress.textContent = `Сохранено цен: ${completed}. Можно вернуться в Avito Check.`;
    form.hidden = true;
    controls.hidden = true;
    status.textContent = '';
    host.dataset.state = 'done';
  }
  async function load() {
    if (busy) return;
    try {
      const result = await send('current');
      if (result.inactive) return;
      build();
      picker.start();
      if (result.done) { done(result.completed); return; }
      product = result.product;
      title.textContent = product.name;
      progress.textContent = `Товар ${result.index} из ${result.total} · сохранено: ${result.completed}`;
      input.value = product.price;
      picker.setMinimum(input.value);
      input.placeholder = product.price ? '' : 'Цена ещё не указана';
      form.hidden = false;
      controls.hidden = false;
      status.textContent = '';
      host.dataset.state = 'ready';
    } catch (error) {
      build();
      showStatus(error.message);
    }
  }
  async function act(action) {
    if (busy || !product) return;
    try {
      const price = action === 'save' ? ResourceAvito.price(input.value) : '';
      pending(true);
      showStatus(action === 'save' ? 'Сохранение…' : 'Переход…', true);
      const result = await send(action, {productId: product.id, price, version: product.recorded_at});
      if (result.done) done(result.completed);
      else if (ResourceAvito.isAvito(result.nextUrl)) location.assign(result.nextUrl);
      else throw new Error('Некорректная ссылка следующего товара. Обновите панель.');
    } catch (error) { showStatus(error.message); }
    finally { pending(false); }
  }
  load();
})();
