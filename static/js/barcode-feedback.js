/* ReSOURCE: Короткий отклик сканера. Ошибка звука не отменяет результат складской формы. */
(() => {
  'use strict';
  const urls = document.body?.dataset || {};
  const blockedKey = 'resource.barcode.audio.blocked';
  const audioStatus = document.querySelector('[data-barcode-audio-status]');
  try { if (audioStatus && sessionStorage.getItem(blockedKey)) audioStatus.hidden = false; } catch (_) {}
  let current = null;
  function playBarcodeFeedback(success) {
    if (current) current();
    const url = success ? urls.barcodeYesSound : urls.barcodeNoSound;
    if (!url) return Promise.resolve(false);
    return new Promise(resolve => {
      let audio;
      try { audio = new Audio(url); } catch (_) { resolve(false); return; }
      audio.volume = 1;
      audio.dataset.notificationChannel = 'barcode';
      let timer, finished = false;
      const finish = played => {
        if (finished) return;
        finished = true;
        clearTimeout(timer);
        audio.pause();
        audio.onended = audio.onerror = null;
        if (current === cancel) current = null;
        if (played) {
          if (audioStatus) audioStatus.hidden = true;
          try { sessionStorage.removeItem(blockedKey); } catch (_) {}
        }
        resolve(played);
      };
      const cancel = () => finish(false);
      current = cancel;
      audio.onended = () => finish(true);
      audio.onerror = () => finish(false);
      timer = setTimeout(cancel, 5000);
      const failed = error => {
        if (error.name === 'NotAllowedError') {
          if (audioStatus) audioStatus.hidden = false;
          try { sessionStorage.setItem(blockedKey, '1'); } catch (_) {}
        }
        finish(false);
      };
      try { Promise.resolve(audio.play()).catch(failed); } catch (error) { failed(error); }
    });
  }
  document.querySelector('[data-enable-barcode-audio]')?.addEventListener('click', async () => {
    if (await playBarcodeFeedback(true)) {
      document.querySelector('[data-barcode-audio-status]').hidden = true;
    }
  });
  window.GameBAT = {...window.GameBAT, playBarcodeFeedback};
})();
