/* Разрешённые команды заказов; Avito не получает ключей или доступа к CRM напрямую. */
(() => {
  'use strict';
  const allowedHosts=new Set(['localhost','127.0.0.1','192.168.0.131']);
  const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  let opening;
  function crm(url){try{const u=new URL(url);return u.protocol==='http:'&&allowedHosts.has(u.hostname)&&!u.username&&!u.password;}catch{return false;}}
  async function connection(){
    if(opening)return opening;
    opening=(async()=>{
      const tabs=await chrome.tabs.query({});
      let tab=tabs.find(t=>crm(t.url)&&new URL(t.url).pathname==='/crm/sales/avito-extension/');
      if(!tab){
        const saved=(await chrome.storage.session.get('resource-orders:connection'))['resource-orders:connection'];
        tab=tabs.find(t=>t.id===saved?.id&&crm(t.url)&&new URL(t.url).origin===saved.origin);
        if(tab&&!new URL(tab.url).pathname.startsWith('/crm/accounts/login/'))tab=await chrome.tabs.update(tab.id,{url:saved.origin+'/crm/sales/avito-extension/'});
      }
      if(!tab){const source=tabs.find(t=>crm(t.url)&&new URL(t.url).pathname.startsWith('/crm/'));
        tab=await chrome.tabs.create({url:(source?new URL(source.url).origin:'http://127.0.0.1:8000')+'/crm/sales/avito-extension/',active:false});}
      const state={id:tab.id,origin:new URL(tab.url).origin};
      await chrome.storage.session.set({'resource-orders:connection':state});
      // После перезагрузки расширения старые вкладки остаются без content script.
      // Проверяем приёмник ДО отправки действия; одновременно соединяющиеся строки
      // используют один opening и не перезагружают вкладку наперегонки.
      let refreshed=false;
      for(let n=0;n<40;n++){
        const current=await chrome.tabs.get(state.id);
        if(!crm(current.url)||new URL(current.url).origin!==state.origin)throw new Error('Вкладка связи CRM перенаправлена на другой адрес.');
        const path=new URL(current.url).pathname;
        if(path.startsWith('/crm/accounts/login/'))throw new Error('Войдите в CRM во вкладке связи заказов Avito.');
        if(current.status!=='loading'&&path==='/crm/sales/avito-extension/'){
          try{
            const pong=await chrome.tabs.sendMessage(state.id,{type:'resource-orders:ping'});
            if(pong?.ok)return state;
          }catch{/* Старый content script потерял контекст после перезапуска. */}
          if(!refreshed){refreshed=true;await chrome.tabs.reload(state.id);}
        }
        await pause(250);
      }
      throw new Error('Не удалось подключить расширение к CRM. Обновите вкладку связи заказов Avito в CRM.');
    })();
    try{return await opening;}finally{opening=null;}
  }
  async function bridge(data){
    const state=await connection();
    for(let n=0;n<20;n++){
      let response;
      try{
        const tab=await chrome.tabs.get(state.id);
        if(!crm(tab.url)||new URL(tab.url).origin!==state.origin)throw new Error('CRM перенаправила вкладку.');
        response=await chrome.tabs.sendMessage(state.id,{type:'resource-orders:bridge',data});
      }catch(error){if(n===19)throw new Error('Откройте вкладку связи заказов Avito в CRM и войдите в аккаунт. '+error.message);await pause(500);continue;}
      if(!response?.ok)throw new Error(response?.message||'Нет ответа CRM.');
      return {...response,origin:state.origin};
    }
  }
  function codeURL(source){
    const u=new URL(source);
    if(u.protocol!=='https:'||!['www.avito.ru','avito.ru','m.avito.ru'].includes(u.hostname)||u.port||u.username||u.password||u.pathname!=='/web/1/barcode/generate'||!u.searchParams.get('content'))throw new Error('Исходный отправительный код Avito не найден.');
    return u.href;
  }
  async function imageFromOrder(order){
    async function extract(label,target){
      const source=codeURL(label.source),symbol=new URL(source);
      // Для Code128 используем подтверждённые Avito тип и payload. Номер из списка не угадывается.
      if(symbol.searchParams.get('barcodeType')==='128')return {symbol:{type:'128',content:symbol.searchParams.get('content')},carrier:label.carrier||order.carrier};
      const kind=(symbol.searchParams.get('barcodeType')||'').toUpperCase().replace(/[_-]/g,'');
      if(['QR','QRCODE'].includes(kind))return {symbol:{type:'QR',content:symbol.searchParams.get('content')},carrier:label.carrier||order.carrier};
      // QR и другие символы могут приходить как SVG или через защищённый redirect.
      // Берём только показанное изображение из собственной временной вкладки:
      // повторный fetch из service worker не нужен, SVG не передаётся в CRM.
      if(!target)return null;
      let ready;
      try{ready=await chrome.tabs.sendMessage(target.tabId,{type:'resource-orders:label_capture'});}
      catch{throw new Error('Прервалась связь с мобильным заказом Avito. Повторите попытку.');}
      if(!ready?.ok)throw new Error((ready?.message||'Не удалось подготовить изображение отправительного кода Avito.')+
        ' Формат кода: '+(symbol.searchParams.get('barcodeType')||'не указан').slice(0,40)+'.');
      if(codeURL(ready.label?.source)!==source)throw new Error('Код Avito изменился во время чтения. Повторите попытку.');
      const clip=ready.clip;
      if(!clip||!['x','y','width','height'].every(key=>typeof clip[key]==='number'&&Number.isFinite(clip[key]))||
        clip.x<0||clip.y<0||clip.x>100000||clip.y>100000||clip.width<20||clip.height<20||clip.width>1000||clip.height>1000)
        throw new Error('Некорректные размеры изображения отправительного кода Avito.');
      const current=await chrome.tabs.get(target.tabId);
      if(!ResourceAvito.isAvito(current.url)||new URL(current.url).pathname!=='/orders/'+order.order_id)
        throw new Error('Avito перенаправил временную вкладку заказа.');
      let screenshot;
      try{
        screenshot=await chrome.debugger.sendCommand(target,'Page.captureScreenshot',{
          format:'png',fromSurface:true,captureBeyondViewport:true,
          clip:{x:clip.x,y:clip.y,width:clip.width,height:clip.height,scale:1}});
      }catch{throw new Error('Не удалось получить изображение кода из мобильной вкладки Avito.');}
      if(typeof screenshot?.data!=='string'||!screenshot.data||screenshot.data.length>2*1024*1024)
        throw new Error('Avito не отдал допустимое изображение отправительного кода.');
      return {image:screenshot.data,carrier:ready.label.carrier||label.carrier||order.carrier};
    }
    // Уже открытый мобильный заказ можно прочитать без новой навигации/эмуляции.
    for(const current of await chrome.tabs.query({})){
      if(!ResourceAvito.isAvito(current.url)||new URL(current.url).pathname!=='/orders/'+order.order_id)continue;
      let result;try{result=await chrome.tabs.sendMessage(current.id,{type:'resource-orders:label'});}catch{continue;}
      if(result?.label){const found=await extract(result.label);if(found)return found;}
    }
    const tab=await chrome.tabs.create({url:'about:blank',active:false});
    const target={tabId:tab.id};
    let attached=false;
    let reason='страница не загрузилась';
    try{
      // UA-заголовка недостаточно: Avito проверяет также JS, Client Hints и viewport.
      // Подключаемся только к созданной нами пустой вкладке, до её первой навигации.
      if(!chrome.debugger)throw new Error('Перезагрузите расширение в opera://extensions: требуется разрешение debugger для мобильного вида.');
      await chrome.debugger.attach(target,'1.3');attached=true;
      await chrome.debugger.sendCommand(target,'Emulation.setUserAgentOverride',{
        userAgent:'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36',
        platform:'Linux armv8l',userAgentMetadata:{brands:[{brand:'Chromium',version:'130'}],
          fullVersionList:[{brand:'Chromium',version:'130.0.0.0'}],platform:'Android',
          platformVersion:'13.0.0',architecture:'arm',model:'Pixel 7',mobile:true}});
      await chrome.debugger.sendCommand(target,'Emulation.setDeviceMetricsOverride',{
        width:412,height:852,screenWidth:412,screenHeight:852,deviceScaleFactor:2.625,mobile:true});
      await chrome.debugger.sendCommand(target,'Emulation.setTouchEmulationEnabled',{enabled:true,maxTouchPoints:5});
      await pause(200);
      await chrome.tabs.update(tab.id,{url:'https://m.avito.ru/orders/'+order.order_id});
      for(let n=0;n<35;n++){
        await pause(700);
        const current=await chrome.tabs.get(tab.id);
        const u=new URL(current.url);
        if(!ResourceAvito.isAvito(current.url)||u.pathname!=='/orders/'+order.order_id){reason='Avito перенаправил страницу';continue;}
        let result;try{result=await chrome.tabs.sendMessage(tab.id,{type:'resource-orders:label'});}catch{reason='расширение не подключилось к мобильной странице';continue;}
        if(!result?.label){reason='в мобильном заказе нет исходного кода';continue;}
        return await extract(result.label,target);
      }
      throw new Error('Не удалось прочитать код: '+reason+'. Откройте мобильный заказ и проверьте доступность штрихкода/QR.');
    }finally{
      if(attached)await chrome.debugger.detach(target).catch(()=>{});
      await chrome.tabs.remove(tab.id).catch(()=>{});
    }
  }
  const busy=new Map();
  chrome.runtime.onMessage.addListener((message,sender,reply)=>{
    if(message?.type!=='resource-orders:action')return false;
    (async()=>{
      if(sender.id!==chrome.runtime.id||sender.frameId!==0||!sender.tab||!ResourceAvito.isAvito(sender.url))throw new Error('Недопустимый источник команды.');
      if(!['lookup','draft','print','print_status','sale_status','cancel_sale'].includes(message.action))throw new Error('Неизвестная команда.');
      if(['sale_status','cancel_sale'].includes(message.action)){
        if(typeof message.order_id!=='string'||!/^\d{1,64}$/.test(message.order_id))throw new Error('Некорректный номер заказа.');
        return bridge({action:message.action,order_id:message.order_id,field:message.field,value:message.value,
          version:message.version,confirmed:message.confirmed,comment:message.comment});
      }
      if(['draft','print'].includes(message.action)){
        const order=message.order;
        if(typeof order?.order_id!=='string'||!/^\d{1,64}$/.test(order.order_id))throw new Error('Некорректный номер заказа.');
        const key=message.action+':'+order.order_id;
        if(busy.has(key))return busy.get(key);
        const task=(async()=>{
          if(message.action==='draft'){
            const result=await bridge({action:'draft',order});
            if(!/^\/crm\/sales\//.test(result.url))throw new Error('Некорректная ссылка CRM.');
            await chrome.tabs.create({url:result.origin+result.url,active:true});return {ok:true};
          }
          const label=await imageFromOrder(order);
          return bridge({action:'print',order:{...order,carrier:label.carrier},image:label.image,symbol:label.symbol,request_id:crypto.randomUUID()});
        })();busy.set(key,task);try{return await task;}finally{busy.delete(key);}
      }
      return bridge(message.action==='lookup'?{action:'lookup',ids:message.ids}:{action:'print_status',job_id:message.job_id});
    })().then(reply,error=>reply({ok:false,message:error.message||'Ошибка расширения.'}));
    return true;
  });
})();
