/* Доставка, оплата и отмена только связанной продажи CRM; цветовые классы приходят из CRM. */
(() => {
  'use strict';
  globalThis.ResourceAvitoSaleControls = function(root, orderId, send, onUpdate) {
    const css=document.createElement('style');
    const layout=document.createElement('style');
    layout.textContent='.crm-statuses{display:flex;gap:8px;align-items:end;flex-wrap:wrap;margin-top:8px}.crm-statuses label{display:grid;gap:4px;font:12px Arial}.crm-statuses select{font-family:Arial}.crm-cancel{color:#922438;border-color:#d38c99}dialog{font:14px Arial;color:#24384a;border:1px solid #a7b2c0;border-radius:8px;padding:20px;width:min(420px,85vw)}dialog::backdrop{background:#0006}dialog h2{font-size:18px;margin-top:0}dialog textarea{box-sizing:border-box;width:100%;min-height:70px;margin-bottom:12px;font:inherit}dialog .buttons{display:flex;justify-content:flex-end;gap:8px}dialog [role=alert]{color:#922438;margin:10px 0}';
    const controls=document.createElement('div');controls.className='crm-statuses';controls.hidden=true;
    layout.textContent+=' .crm-statuses[hidden]{display:none}.sale-status{box-sizing:border-box}';
    const dialog=document.createElement('dialog');dialog.setAttribute('aria-label','Подтверждение изменения продажи CRM');
    const form=document.createElement('form');
    const title=document.createElement('h2');
    const question=document.createElement('p');
    const commentLabel=document.createElement('label');commentLabel.textContent='Причина отмены';
    const comment=document.createElement('textarea');comment.setAttribute('aria-label','Причина отмены');comment.maxLength=2000;
    commentLabel.append(comment);
    const error=document.createElement('p');error.setAttribute('role','alert');
    const buttons=document.createElement('div');buttons.className='buttons';
    const back=document.createElement('button');back.type='button';back.textContent='Назад';
    const confirm=document.createElement('button');confirm.type='submit';confirm.textContent='Подтвердить';
    buttons.append(back,confirm);form.append(title,question,commentLabel,error,buttons);dialog.append(form);
    root.append(css,layout,controls,dialog);
    let info, signature='',pending=null,busy=false;
    function ask(action,field,value,label) {
      if(busy||!info?.sale)return;
      pending={action,order_id:orderId,version:info.sale.version,field,value,confirmed:true};
      confirm.hidden=false;
      const cancelling=action==='cancel_sale';
      title.textContent=cancelling?'Удалить продажу — отменить с возвратом':'Изменить статус продажи';
      question.textContent=cancelling?`${info.sale_number}: отменить продажу, вернуть товары и сторнировать её расчёты?`:
        field==='payment'?`${info.sale_number}: подтвердить полную оплату ${info.sale.total} ₽ (${info.sale.payment_method_label})?`:
        `${info.sale_number}: установить статус доставки «${label}»?`;
      commentLabel.hidden=!cancelling;comment.required=cancelling;comment.value='';error.textContent='';
      confirm.textContent=cancelling?'Отменить продажу с возвратом':'Подтвердить';
      dialog.showModal();(cancelling?comment:confirm).focus();
    }
    back.onclick=()=>{pending=null;dialog.close();};
    dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();else pending=null;});
    async function refresh() {
      const result=await send('lookup',{ids:[orderId]});
      onUpdate(result.orders[orderId],result.status_css,result.origin);
    }
    form.onsubmit=async event=>{
      event.preventDefault();if(busy||!pending)return;
      busy=true;confirm.disabled=back.disabled=true;
      controls.querySelectorAll('button,select').forEach(el=>el.disabled=true);
      try {
        const result=await send(pending.action,{...pending,comment:comment.value.trim()});
        onUpdate(result.order);pending=null;dialog.close();
      } catch(problem) {
        error.textContent=problem.message;
        // Ответ мог потеряться после проведения: сверяемся с CRM перед новым действием.
        pending=null;confirm.hidden=true;
        try{await refresh();}catch{/* Ошибка остаётся видна; следующий lookup обновит строку. */}
      } finally {
        busy=false;confirm.disabled=back.disabled=false;
        signature='';render();
      }
    };
    function statusField(name,field,value,label,next,nextLabel) {
      const wrapper=document.createElement('label');wrapper.textContent=name;
      const select=document.createElement('select');select.className='sale-status sale-status-'+value;
      select.setAttribute('aria-label',name);
      select.add(new Option(label,value));
      if(next)select.add(new Option(nextLabel,next));
      select.disabled=busy||!next;
      select.onchange=()=>{const chosen=select.value;select.value=value;if(chosen!==value)ask('sale_status',field,chosen,nextLabel);};
      wrapper.append(select);controls.append(wrapper);
    }
    function render() {
      const state=info?.sale;
      const key=JSON.stringify(state);
      if(key===signature)return;signature=key;
      controls.replaceChildren();controls.hidden=!state;
      if(!state)return;
      if(state.cancelled){
        const badge=document.createElement('span');badge.className='sale-status sale-status-cancelled';badge.textContent='Продажа отменена';controls.append(badge);return;
      }
      statusField('Доставка CRM','order',state.order_status,state.order_label,state.next_order,state.next_order_label);
      statusField('Оплата CRM','payment',state.payment_status,state.payment_label,state.can_mark_paid?'paid':null,'Оплачен');
      if(state.can_cancel){
        const remove=document.createElement('button');remove.type='button';remove.className='crm-cancel';remove.textContent='Удалить продажу';remove.disabled=busy;
        remove.onclick=()=>ask('cancel_sale');controls.append(remove);
      }
    }
    return {update(next,styles){
      info=next;if(styles&&css.textContent!==styles)css.textContent=styles;
      render();
      if(!dialog.open){confirm.hidden=false;error.textContent='';}
    }};
  };
})();
