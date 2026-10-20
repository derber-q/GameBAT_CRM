(() => {
  const dialog = document.getElementById('sale-market-cancel-dialog');
  const question = document.getElementById('sale-market-cancel-question');
  const confirmation = document.getElementById('sale-market-cancel-confirm-form');
  const back = document.getElementById('sale-market-cancel-back');
  if (!dialog || !question || !confirmation || !back) return;
  let pendingForm;

  // Делегирование работает и после AJAX-замены строки продажи.
  document.addEventListener('submit', (event) => {
    const form = event.target.closest('[data-market-action]');
    if (!form || form.dataset.marketAction !== 'cancel') return;
    event.preventDefault();
    pendingForm = form;
    form.querySelector('[name="confirm"]').value = '';
    question.textContent = `Запрос на отмену заказа №${form.dataset.marketOrderNumber} будет отправлен в Яндекс Маркет.`;
    dialog.showModal();
  });
  dialog.addEventListener('cancel', () => {pendingForm = null;});
  dialog.addEventListener('close', () => {pendingForm = null;});
  back.addEventListener('click', () => {pendingForm = null; dialog.close();});
  confirmation.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!pendingForm) return;
    const form = pendingForm;
    pendingForm = null;
    form.querySelector('[name="confirm"]').value = 'yes';
    dialog.close();
    form.submit();
  });
})();
