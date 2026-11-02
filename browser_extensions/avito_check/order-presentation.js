/* Фотографии и фон строки Avito: без изменения данных и высоты исходной строки. */
(() => {
  'use strict';
  globalThis.ResourceAvitoOrderPresentation = function(row, initialOrder, actions) {
    const host=document.createElement('resource-avito-products');
    host.style.cssText='position:absolute;z-index:2;display:none';
    const root=host.attachShadow({mode:'open'});
    const style=document.createElement('style');
    style.textContent=`
      :host{font:13px/14px Arial;color:#111}
      .products{display:flex;gap:12px;overflow-x:auto;overflow-y:hidden;height:100%;scrollbar-width:thin}
      a{flex:0 0 min(var(--product-width,180px),100%);min-width:0;display:grid;grid-template-rows:var(--photo-height) 28px;gap:4px;color:inherit;text-decoration:none}
      a:focus-visible{outline:2px solid #237e90;outline-offset:-2px;border-radius:8px}
      img{width:100%;height:100%;object-fit:contain;border-radius:8px;background:#f3f5f7}
      span{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;overflow-wrap:anywhere;text-align:center}
    `;
    const products=document.createElement('div');products.className='products';
    root.append(style,products);row.append(host);row.classList.add('resource-avito-order-row');
    let order=initialOrder, info, known=false, originals=[], signature='',frame;
    function showOriginals(){originals.forEach(group=>group.classList.remove('resource-order-images-muted'));}
    function paint() {
      let state='unknown';
      if(/отмен/i.test(order.status)||info?.cancelled)state='cancelled';
      else if(known&&!info?.sale_url)state='unlinked';
      else if(known){
        if(/Едет к покупателю|Жд[её]т выдачи покупателю/i.test(order.status))state='transit';
        else if(/Получите оплату/i.test(order.status))state='payment';
        else state='ready';
      }
      row.dataset.resourceOrderState=state;
    }
    function layout() {
      // У каждого товара Avito свой images-row; выбор только первого теряет состав заказа.
      const groups=Array.from(row.querySelectorAll('[data-marker="images-row"]'));
      const group=groups[0],images=groups.flatMap(node=>Array.from(node.querySelectorAll('img[alt]')));
      const key=JSON.stringify(images.map(img=>[img.getAttribute('src'),img.currentSrc,img.alt]));
      originals.filter(node=>!groups.includes(node)).forEach(node=>node.classList.remove('resource-order-images-muted'));
      originals=groups;
      if(!group||!images.length){host.style.display='none';showOriginals();return;}
      if(key!==signature){
        signature=key;products.replaceChildren();
        const url=Array.from(row.querySelectorAll('a[href]')).find(a=>/^\/orders\/\d+/.test(a.getAttribute('href')))?.getAttribute('href');
        for(const image of images){
          const card=document.createElement('a');if(url)card.setAttribute('href',url);
          const photo=document.createElement('img');
          const source=image.currentSrc||image.getAttribute('src');if(source)photo.src=source;
          photo.alt=image.alt;photo.decoding='async';
          const name=document.createElement('span');name.textContent=image.alt;card.title=image.alt;
          card.append(photo,name);products.append(card);
        }
      }
      // Абсолютный блок занимает свободное место справа, а исходные фото сохраняют
      // свой размер в потоке. Увеличение изображения не раздвигает соседние заказы.
      const bounds=row.getBoundingClientRect(), source=group.getBoundingClientRect();
      if(!bounds.width||!bounds.height){host.style.display='none';showOriginals();return;}
      const controls=Array.from(actions.shadowRoot.querySelectorAll('.actions > *, .crm-statuses > *'))
        .map(el=>el.getBoundingClientRect()).filter(rect=>rect.width&&rect.height);
      let left=Math.max(0,source.left-bounds.left),top=Math.max(0,source.top-bounds.top);
      const safeLeft=Math.max(left,...controls.map(rect=>rect.right-bounds.left+12));
      if(bounds.width-safeLeft>=144)left=safeLeft;
      const width=Math.min(460,bounds.width-left-4);
      let available=bounds.height-top-4;
      for(const rect of controls){
        if(rect.right>bounds.left+left&&rect.left<bounds.left+left+width&&rect.top>=source.top)
          available=Math.min(available,rect.top-source.top-4);
      }
      // Для нескольких товаров оставляем место полосе прокрутки внутри блока.
      const scrollSpace=images.length>1?12:0;
      const photoHeight=Math.min(108,Math.floor(available-32-scrollSpace));
      if(width<80||photoHeight<24){host.style.display='none';showOriginals();return;}
      // Два-три товара делят ширину ленты; большие заказы остаются в одном ряду с прокруткой.
      const productWidth=Math.min(180,Math.max(112,Math.floor((width-12*(images.length-1))/images.length)));
      groups.forEach(node=>node.classList.add('resource-order-images-muted'));
      host.style.cssText=`position:absolute;z-index:2;left:${left}px;top:${top}px;width:${width}px;height:${photoHeight+32+scrollSpace}px;--photo-height:${photoHeight}px;--product-width:${productWidth}px;`;
    }
    function schedule() {if(frame)cancelAnimationFrame(frame);frame=requestAnimationFrame(layout);}
    const resize=new ResizeObserver(schedule);resize.observe(row);
    paint();schedule();
    return {
      setOrder(next){order=next;paint();schedule();},
      update(next){info=next;known=true;paint();schedule();},
      dispose(){resize.disconnect();if(frame)cancelAnimationFrame(frame);showOriginals();host.remove();row.classList.remove('resource-avito-order-row');delete row.dataset.resourceOrderState;}
    };
  };
})();
