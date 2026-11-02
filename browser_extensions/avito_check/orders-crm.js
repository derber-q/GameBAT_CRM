/* Мост session/CSRF только на фиксированном маршруте CRM. */
(() => {
  'use strict';
  if(location.pathname!=='/crm/sales/avito-extension/')return;
  chrome.runtime.onMessage.addListener((message,sender,reply)=>{
    if(!['resource-orders:bridge','resource-orders:ping'].includes(message?.type) || sender.id!==chrome.runtime.id || sender.tab)return false;
    const csrf=document.getElementById('avito-extension-csrf')?.value;
    if(!csrf){reply({ok:false,message:'Войдите в CRM и откройте вкладку связи заказов Avito.'});return false;}
    if(message.type==='resource-orders:ping'){reply({ok:true});return false;}
    fetch(location.pathname,{method:'POST',credentials:'same-origin',cache:'no-store',redirect:'error',
      headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify(message.data),signal:AbortSignal.timeout(20000)})
      .then(async response=>{if(!(response.headers.get('content-type')||'').includes('application/json'))throw new Error('Войдите в CRM.');return response.json();})
      .then(reply,error=>reply({ok:false,message:error.message==='Failed to fetch'?
        'Нет связи с CRM. Проверьте, что сайт CRM запущен, и обновите вкладку связи.':error.message||'Нет связи с CRM.'}));
    return true;
  });
})();
