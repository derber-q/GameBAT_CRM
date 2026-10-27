(() => {
  const controls = document.querySelector('[data-sales-channels]');
  if (!controls) return;
  const buttons = controls.querySelectorAll('[data-sales-channel]');
  const empty = document.querySelector('[data-sales-channel-empty]');
  let channel = 'all';
  function update() {
    let visible = 0;
    document.querySelectorAll('[data-sale-group]').forEach((group) => {
      const count = Number(group.querySelector('[data-sale-count]')?.textContent || 0);
      group.hidden = count === 0 || (channel !== 'all' && group.dataset.saleGroup !== channel);
      if (!group.hidden) visible++;
    });
    buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.salesChannel === channel)));
    if (empty) {
      empty.hidden = visible > 0;
      empty.textContent = channel === 'all' ? 'Продаж нет.' : 'Продаж в этой категории нет';
    }
  }
  controls.addEventListener('click', (event) => {
    const button = event.target.closest('[data-sales-channel]');
    if (!button) return;
    channel = button.dataset.salesChannel;
    update();
  });
  window.GameBAT = {...window.GameBAT, refreshSalesChannels: update};
  window.addEventListener('pageshow', event => {
    if (event.persisted) {channel = 'all'; update();}
  });
  update();
})();
