/* Заказы Avito: только видимые данные текущей страницы, без изменения заказа на Avito. */
(() => {
  'use strict';
  const carriers = ['Почта России', 'Яндекс Доставка', 'ЯндексДоставка', 'СДЭК', '5Post', 'Boxberry', 'DPD', 'Авито', 'Avito'];
  const normalize = text => String(text || '').replace(/\s+/g, ' ').trim();
  function hasShippingCode(order) {
    const method=normalize(order.carrier);
    // У Достависты курьерская передача без отправительного кода пункта приёма.
    if(/^(?:достависта|dostavista)$/i.test(method))return false;
    // Общее «Доставка» означает доставку продавца; остальные службы не исключаем.
    return !/^(?:самовывоз(?:\s|$)|доставка$|доставка\s+(?:продавц|силами продавца|своими силами|курьером))/i.test(method);
  }
  function rowData(row) {
    const link = Array.from(row.querySelectorAll('a[href]')).find(a => /^\/orders\/\d+/.test(a.getAttribute('href')));
    const id = link?.getAttribute('href').match(/^\/orders\/(\d+)/)?.[1];
    if (!id) return null;
    const nodes = Array.from(row.querySelectorAll('p'));
    const paragraphs = nodes.map(p => normalize(p.textContent));
    const priceIndex = paragraphs.findIndex(t => /^[\d\s]+(?:[,.]\d{1,2})?\s*₽/.test(t));
    const sibling=nodes[priceIndex]?.nextElementSibling;
    const candidate=sibling?.matches('p')?normalize(sibling.textContent):'';
    const carrier = paragraphs.find(t => carriers.some(c => t.toLowerCase() === c.toLowerCase())) ||
      (candidate&&candidate.length<=100&&!/₽/.test(candidate)&&/[A-Za-zА-Яа-яЁё]/.test(candidate)?candidate:'');
    const price = paragraphs[priceIndex];
    return {order_id:id, carrier, amount:price ? price.split('₽')[0].replace(/\s/g,'').replace(',','.') : null,
      titles:Array.from(row.querySelectorAll('[data-marker="images-row"] img[alt]')).map(n => normalize(n.alt)).filter(Boolean),
      status:normalize(row.querySelector('[data-marker="order-status"]')?.textContent)};
  }
  function labelData() {
    const img = Array.from(document.images).find(image => {
      try { const u = new URL(image.src); return ['avito.ru','www.avito.ru','m.avito.ru'].includes(u.hostname) && u.pathname === '/web/1/barcode/generate'; }
      catch { return false; }
    });
    if (!img) return null;
    // Контекст названия берётся из блока отправки, а не меню/рекламы сайта.
    const text = normalize(document.body.innerText);
    const heading = text.match(/Отправьте заказ через[^.\n]{0,120}/)?.[0] || '';
    const carrier = /Почт[аы]/i.test(heading) ? 'Почта России' : carriers.find(c => heading.toLowerCase().includes(c.toLowerCase()));
    return {source:img.src, carrier:carrier || ''};
  }
  globalThis.ResourceAvitoOrders = {rowData, labelData};
  chrome.runtime.onMessage.addListener((message, sender, reply) => {
    if (sender.id !== chrome.runtime.id || sender.tab || message?.type !== 'resource-orders:label') return false;
    reply({ok:true, label:labelData()});
  });
  if (!['avito.ru','www.avito.ru','m.avito.ru'].includes(location.hostname) || !location.pathname.startsWith('/orders')) return;
  const seen = new WeakMap();
  let updating = false;
  async function send(action, data = {}) {
    const response = await chrome.runtime.sendMessage({type:'resource-orders:action', action, ...data});
    if (!response?.ok) throw new Error(response?.message || 'CRM не ответила. Проверьте подключение.');
    return response;
  }
  function ui(row, order) {
    const host = document.createElement('resource-avito-order');
    host.style.cssText = 'position:relative;z-index:5;display:block;margin:8px 0 12px;';
    const root = host.attachShadow({mode:'open'});
    const style = document.createElement('style');
    style.textContent = ':host{font:13px Arial;color:#24384a}.actions{display:flex;gap:8px;flex-wrap:wrap}button,a{font:inherit;padding:8px 10px;border:1px solid #237e90;border-radius:6px;background:#fff;color:#176d7e;cursor:pointer;text-decoration:none}button:disabled{opacity:.55;cursor:wait}small{display:block;max-width:430px;margin-top:6px;line-height:1.4}';
    root.append(style);
    const actions = document.createElement('div'); actions.className='actions';root.append(actions);
    const sale = document.createElement('button');sale.textContent='Создать продажу';actions.append(sale);
    const print = document.createElement('button');print.textContent='Напечатать отправительный код';
    if(hasShippingCode(order))actions.append(print);
    const status = document.createElement('small');status.setAttribute('role','status');root.append(status);
    let crmOrigin='';
    function showInfo(info,styles,origin) {
      if(origin)crmOrigin=origin;
      saleControls.update(info,styles);
      presentation.update(info);
      if(info?.sale_url) {
        if(!saleLink){saleLink=document.createElement('a');saleLink.target='_blank';saleLink.rel='noopener';sale.replaceWith(saleLink);}
        saleLink.href=crmOrigin+info.sale_url;saleLink.textContent=info.sale_number+(info.cancelled?' · отменена':'');
      }
    }
    const saleControls=ResourceAvitoSaleControls(root,order.order_id,send,showInfo);
    let cancelled = /отмен/i.test(order.status);
    let saleLink;
    sale.disabled=print.disabled=cancelled;
    for (const name of ['click','pointerdown','mousedown']) host.addEventListener(name,e => e.stopPropagation());
    row.append(host);
    const presentation=ResourceAvitoOrderPresentation(row,order,host);
    let busy=false;
    let connectionError='';
    async function act(action) {
      if (busy || (action==='print'&&!hasShippingCode(order))) return; busy=true;sale.disabled=print.disabled=true;
      status.textContent=action==='draft'?'Открытие формы CRM…':'Чтение оригинального кода заказа…';
      try {
        const result=await send(action,{order});
        if (action==='draft') status.textContent='Форма открыта в CRM. После сохранения здесь появится номер продажи.';
        else {
          status.textContent='Стикер передан в очередь печати.';
          for (let n=0;n<90;n++) {
            await new Promise(resolve=>setTimeout(resolve,1500));
            const state=await send('print_status',{job_id:result.job_id});
            if (state.state==='done') {status.textContent='Стикер напечатан.';break;}
            if (['error','uncertain'].includes(state.state)) throw new Error(state.message || 'Печать не подтверждена. Проверьте принтер.');
            if(n===89) status.textContent='Задание остаётся в очереди. Проверьте агент/обработчик печати; повторно не нажимайте.';
          }
        }
      } catch(error) {status.textContent=error.message;}
      finally {busy=false;sale.disabled=print.disabled=cancelled;}
    }
    sale.onclick=()=>act('draft');print.onclick=()=>act('print');
    return {order, host, setOrder(next) {
      order=next;this.order=next;cancelled=/отмен/i.test(order.status);
      presentation.setOrder(next);
      if(hasShippingCode(order)){if(print.parentNode!==actions)actions.append(print);}
      else print.remove();
      if(!busy)sale.disabled=print.disabled=cancelled;
    }, dispose(){presentation.dispose();host.remove();}, connectionFailed(message) {
      if(!busy && (!status.textContent || status.textContent===connectionError)) {
        status.textContent=message;connectionError=message;
      }
    }, update(info,origin,styles) {
      if(!busy && connectionError && status.textContent===connectionError)status.textContent='';
      connectionError='';
      showInfo(info,styles,origin);
    }};
  }
  async function update() {
    if(updating)return;updating=true;
    const rows=[];
    try {
      for(const row of document.querySelectorAll('[data-marker="order-row"]')) {
        const data=rowData(row);
        // Не добавляем продажу к покупкам пользователя: нужен явно продавцовский статус.
        if(!data)continue;
        const seller=/Отправьте заказ|Получите оплату|Едет к покупателю|Жд[её]т выдачи покупателю/i.test(data.status) ||
          (/Заверш[её]н/i.test(data.status) && /Банк перев[её]л/i.test(normalize(row.textContent)));
        if(!seller && !/Отмен[её]н/i.test(data.status))continue;
        let item=seen.get(row);
        if(item?.order.order_id!==data.order_id){item?.dispose();item=ui(row,data);seen.set(row,item);}
        else item.setOrder(data);
        rows.push(item);
      }
      if(!rows.length)return;
      for(let i=0;i<rows.length;i+=100){
        const batch=rows.slice(i,i+100),response=await send('lookup',{ids:batch.map(r=>r.order.order_id)});
        batch.forEach(r=>r.update(response.orders[r.order.order_id],response.origin,response.status_css));
      }
    } catch(error) {
      for(const row of rows)row.connectionFailed(error.message);
    } finally {updating=false;}
  }
  let timer;
  new MutationObserver(()=>{clearTimeout(timer);timer=setTimeout(update,600);}).observe(document.body,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['alt','src','srcset']});
  update();setInterval(update,15000);
})();
