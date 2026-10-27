((root, factory) => {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.GameBAT = {...root.GameBAT, marketAlertState: api};
})(typeof window !== 'undefined' ? window : globalThis, () => {
  const LEASE_MS = 60000;
  function cycleFor(order, now, period = 600000) {
    const start = Date.parse(order.started_at);
    return Number.isFinite(start) && now >= start ? Math.floor((now - start) / period) : -1;
  }
  function chooseOrder(orders, seen, now, period = 600000) {
    return orders.map(order => ({order, cycle: cycleFor(order, now, period)}))
      .filter(item => item.cycle >= 0 && item.cycle > (seen.get(String(item.order.id)) ?? -1))
      .sort((a, b) => (Date.parse(a.order.started_at) + a.cycle * period)
        - (Date.parse(b.order.started_at) + b.cycle * period) || Number(a.order.id) - Number(b.order.id))[0] || null;
  }
  class IndexedState {
    constructor(idb = globalThis.indexedDB) {
      this.ready = new Promise((resolve, reject) => {
        if (!idb) {reject(new Error('Браузер не поддерживает координацию вкладок.')); return;}
        const request = idb.open('gamebat-market-alerts', 1);
        request.onupgradeneeded = () => request.result.createObjectStore('state', {keyPath: 'key'});
        request.onerror = () => reject(request.error);
        request.onblocked = () => reject(new Error('Хранилище уведомлений заблокировано другой вкладкой.'));
        request.onsuccess = () => {
          const db = request.result;
          db.onversionchange = () => db.close();
          resolve(db);
        };
      });
    }
    async run(change) {
      const db = await this.ready;
      return new Promise((resolve, reject) => {
        const transaction = db.transaction('state', 'readwrite');
        const store = transaction.objectStore('state');
        let result;
        const read = store.getAll();
        read.onsuccess = () => {
          try {result = change(new Map(read.result.map(row => [row.key, row])), store);}
          catch (error) {transaction.abort(); reject(error);}
        };
        transaction.oncomplete = () => resolve(result);
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error || new Error('Транзакция уведомлений прервана.'));
      });
    }
    enabled() {return this.run(values => !!values.get('enabled')?.value);}
    enable() {return this.run((values, store) => store.put({key: 'enabled', value: true}));}
    claim(orders, now, owner, period = 600000, test = false) {
      return this.run((values, store) => {
        const wall = Date.now();
        if ((values.get('speaker')?.expires || 0) > wall) return null;
        const seen = new Map([...values.values()].filter(row => row.key.startsWith('cycle:'))
          .map(row => [row.key.slice(6), row.cycle]));
        const next = test ? {order: null, cycle: null} : chooseOrder(orders, seen, now, period);
        if (!next) return null;
        const lease = {key: 'speaker', owner, token: `${owner}:${wall}:${Math.random()}`,
          expires: wall + LEASE_MS, orderId: next.order?.id ?? null, cycle: next.cycle};
        store.put(lease);
        return lease;
      });
    }
    started(lease) {
      return this.run((values, store) => {
        if (values.get('speaker')?.token !== lease.token) return false;
        if (lease.orderId !== null) store.put({key: `cycle:${lease.orderId}`, cycle: lease.cycle});
        return true;
      });
    }
    renew(lease) {
      return this.run((values, store) => {
        const current = values.get('speaker');
        if (current?.token !== lease.token) return false;
        store.put({...current, expires: Date.now() + LEASE_MS});
        return true;
      });
    }
    release(lease) {
      return this.run((values, store) => {
        if (values.get('speaker')?.token === lease.token) store.delete('speaker');
      });
    }
  }
  return {cycleFor, chooseOrder, IndexedState};
});
