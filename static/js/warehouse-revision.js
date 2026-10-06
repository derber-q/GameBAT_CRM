(() => {
  'use strict';
  const list = document.querySelector('[data-revision-list]');
  if (!list) return;
  const dialog = document.querySelector('[data-revision-dialog]');
  document.querySelector('[data-revision-new]')?.addEventListener('click', () => dialog.showModal());
  document.querySelector('[data-revision-cancel]')?.addEventListener('click', () => dialog.close());
  dialog?.querySelector('form').addEventListener('submit', () => {
    dialog.querySelector('[type="submit"]').disabled = true;
  });
  // Последовательные запросы не позволяют более старому ответу затереть прогресс.
  let queue = Promise.resolve();
  list.querySelectorAll('[data-revision-check]').forEach(input => {
    input.addEventListener('change', () => {
      const card = input.closest('[data-revision-card]');
      const feedback = card.querySelector('[data-revision-feedback]');
      const desired = input.checked;
      const previous = card.classList.contains('is-checked');
      input.checked = previous;
      input.disabled = true;
      card.classList.remove('has-error');
      feedback.textContent = 'Сохранение…';
      queue = queue.then(async () => {
        const data = new FormData();
        data.set('csrfmiddlewaretoken', list.querySelector('[name="csrfmiddlewaretoken"]').value);
        data.set('revision_id', list.dataset.revisionId);
        data.set('kind', card.dataset.kind);
        data.set('product_id', card.dataset.productId);
        data.set('checked', String(desired));
        try {
          const response = await fetch(list.dataset.checkUrl, {
            method: 'POST', body: data, credentials: 'same-origin',
            headers: {'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
          });
          if (!(response.headers.get('content-type') || '').includes('application/json')) {
            throw new Error('Проверьте вход в аккаунт и доступ к складу, затем обновите страницу.');
          }
          const result = await response.json();
          if (!response.ok || !result.ok) throw new Error(result.message || 'Не удалось сохранить отметку.');
          list.dataset.revisionId = String(result.revision_id);
          const cycleInput = dialog?.querySelector('[name="revision_id"]');
          if (cycleInput) cycleInput.value = result.revision_id;
          const initialNotice = document.querySelector('[data-revision-initial]');
          if (initialNotice) initialNotice.textContent = `Ревизия №${result.revision_id}. Отметки общие для склада.`;
          input.checked = result.checked;
          card.classList.toggle('is-checked', result.checked);
          card.querySelector('[data-quantity]').textContent = result.quantity;
          document.querySelector('[data-progress-count]').textContent = `${result.progress.checked} / ${result.progress.total}`;
          document.querySelector('[data-progress-percent]').textContent = `${String(result.progress.percent).replace('.', ',')}%`;
          const bar = document.querySelector('[data-progress-bar]');
          bar.max = result.progress.total || 1;
          bar.value = result.progress.checked;
          feedback.textContent = 'Сохранено';
        } catch (error) {
          input.checked = previous;
          card.classList.add('has-error');
          feedback.textContent = error.message || 'Нет соединения. Повторите попытку.';
        } finally {
          input.disabled = false;
        }
      });
    });
  });
})();
