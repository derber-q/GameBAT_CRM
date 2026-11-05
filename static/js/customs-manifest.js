/* Форма остаётся на странице при ошибке: сервер получает один JSON-параметр. */
document.addEventListener('DOMContentLoaded', () => {
  const form=document.querySelector('[data-customs-form]');if(!form)return;
  const rows=Array.from(form.querySelectorAll('[data-customs-row]'));
  const message=form.querySelector('[data-customs-message]');let busy=false;
  const confirmed=row=>JSON.parse(row.dataset.confirmed||'[]');
  const fields=row=>Array.from(row.querySelectorAll('[data-field]'));
  const nonempty=row=>fields(row).filter(f=>!['quantity','number'].includes(f.dataset.field)&&f.value.trim()).map(f=>f.dataset.field);
  const state=row=>{
    const entered=row.querySelector('[data-field=quantity]').value.trim();
    const valid=/^[0-9]{1,19}$/.test(entered)&&BigInt(entered)<=9223372036854775807n;
    row.querySelector('[data-field=quantity]').setAttribute('aria-invalid',String(!valid));
    const difference=valid&&BigInt(entered)!==BigInt(row.dataset.expected);
    row.classList.toggle('customs-quantity-difference',difference);
    row.querySelector('[data-quantity-correction]').hidden=!difference;
    const verified=confirmed(row);
    row.querySelector('[data-confirm-row]').checked=nonempty(row).every(f=>verified.includes(f));
    row.querySelector('[data-en-warning]').hidden=verified.includes('en_description');
  };
  const totals=()=>{
    let total=0n,valid=true;
    for(const row of rows){const value=row.querySelector('[data-field=quantity]').value.trim();
      if(!/^[0-9]{1,19}$/.test(value)||BigInt(value)>9223372036854775807n){valid=false;continue;}total+=BigInt(value);}
    document.querySelector('[data-customs-total]').textContent=valid?total.toLocaleString('ru-RU'):'—';
  };
  rows.forEach(row=>{
    row.querySelector('[data-confirm-row]').addEventListener('change',event=>{
      row.dataset.confirmed=JSON.stringify(event.target.checked?nonempty(row):[]);state(row);
    });
    fields(row).forEach(field=>field.addEventListener('input',()=>{
      row.dataset.confirmed=JSON.stringify(confirmed(row).filter(f=>f!==field.dataset.field));state(row);totals();
      form.querySelector('[data-customs-ack]').checked=false;
    }));state(row);
  });
  const dataFor=row=>{
    const data={stable_key:row.dataset.key,confirmed_fields:confirmed(row)};
    fields(row).forEach(f=>data[f.dataset.field]=f.value);
    data.quantity_reason=row.querySelector('[data-quantity-reason]').value;
    data.quantity_confirmed=row.querySelector('[data-quantity-confirmed]').checked;
    return data;
  };
  form.addEventListener('submit',event=>event.preventDefault());
  form.querySelectorAll('[data-customs-action]').forEach(button=>button.addEventListener('click',async()=>{
    if(busy||button.disabled)return;
    const action=button.dataset.customsAction;
    if(action==='defaults'&&!window.confirm('Сохранить подтверждённые характеристики для будущих рейсов? Это отдельное изменение общего справочника.'))return;
    if(action==='refresh'&&!window.confirm('Обновить фактический состав? Однозначные исправления сохранятся. Прежняя редакция останется в истории; корректировки количества потребуется проверить заново.'))return;
    const payload={action,revision:form.dataset.revision,source_signature:form.dataset.signature,
      acknowledged:form.querySelector('[data-customs-ack]').checked,rows:rows.map(dataFor)};
    if(action==='defaults'){
      const row=button.closest('[data-customs-row]');Object.assign(payload,{key:row.dataset.key,row:dataFor(row),
        target:button.dataset.target,product:row.querySelector('[data-default-product]').value});
    }
    busy=true;message.textContent='Сохраняется…';message.className='muted';
    try{
      const body=new FormData();body.set('csrfmiddlewaretoken',form.querySelector('[name=csrfmiddlewaretoken]').value);
      body.set('payload',JSON.stringify(payload));
      const response=await fetch(form.action||window.location.href,{method:'POST',credentials:'same-origin',
        headers:{'X-Requested-With':'XMLHttpRequest','Accept':'application/json'},body});
      if(!response.headers.get('Content-Type')?.includes('application/json'))throw Error('Нет доступа к действию или срок входа истёк. Войдите в CRM; введённые данные остаются в форме.');
      const result=await response.json();if(!response.ok||!result.ok)throw Error(result.error||'Нет доступа к действию. Обновите страницу после входа.');
      message.textContent=result.message;message.className='alert alert-success';
      if(result.revision){form.dataset.revision=String(result.revision);form.dataset.signature=result.source_signature;
        document.querySelector('[data-customs-revision]').textContent=String(result.revision);}
      if(result.warnings){const list=form.querySelector('[data-customs-warnings]');list.replaceChildren();
        for(const text of result.warnings.length?result.warnings:['Незаполненных и непроверенных характеристик не обнаружено.']){
          const li=document.createElement('li');li.textContent=text;list.append(li);}}
      if(result.refresh_url)window.location.assign(result.refresh_url);
      else if(result.download_url)window.location.assign(result.download_url);
    }catch(error){message.textContent=error.message||'Не удалось сохранить. Введённые данные остаются в форме.';message.className='alert alert-error';}
    finally{busy=false;}
  }));totals();
});
