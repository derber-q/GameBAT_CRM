"""Два независимых потока; GUI обновляется через очередь, не из worker-потоков."""
import json
import os
import queue
import threading
import uuid
from pathlib import Path
from . import VERSION
from .journal import BackupJournal
from .downloads import download,cleanup
from .transport import BackupAPI
from print_agent.__main__ import exclusive


class Runtime:
    def __init__(self,folder,get_config):
        self.folder,self.get_config=folder,get_config
        self.stop=threading.Event();self.events=queue.Queue(maxsize=100)
        self.request_lock=threading.RLock()
        self.session=uuid.uuid4()
        self.print_instance=uuid.uuid4()
        self.threads=[]

    def start(self):
        for target in (self.backup_loop,self.print_loop):
            thread=threading.Thread(target=target,daemon=True);thread.start();self.threads.append(thread)

    def report(self,channel,text):
        try: self.events.put_nowait((channel,text))
        except queue.Full: pass

    def request_backup(self):
        """Один UUID переживает повторный клик, потерю ответа и перезапуск."""
        path=self.folder/'backup-request.json'
        with self.request_lock:
            if path.exists():return uuid.UUID(json.loads(path.read_text())['request_id'])
            request_id=uuid.uuid4();self.save_request({'request_id':str(request_id)})
            return request_id

    def save_request(self,value):
        path=self.folder/'backup-request.json';temporary=path.with_suffix('.tmp')
        with self.request_lock,temporary.open('w',encoding='utf-8') as stream:
            json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)

    def backup_loop(self):
        journal=BackupJournal(self.folder/'backups.sqlite3')
        try:
            while not self.stop.is_set():
                config=self.get_config()
                try:
                    if config.get('backup_enabled') and config.get('backup_token'):
                        api=BackupAPI(config,self.session);api.heartbeat()
                        # UUID команды сохраняется ДО HTTP и переживает перезапуск.
                        command_path=self.folder/'backup-request.json'
                        pending=None
                        if command_path.exists():
                            pending=json.loads(command_path.read_text())
                            if not pending.get('job_id'):
                                response=api.create(uuid.UUID(pending['request_id']))
                                pending['job_id']=str(uuid.UUID(response['id']))
                                self.save_request(pending)
                        jobs=api.status()
                        if pending:
                            terminal=next((j for j in jobs if j['id']==pending.get('job_id') and j['state'] in ('error','expired','skipped')),None)
                            if terminal:
                                with self.request_lock:command_path.unlink(missing_ok=True)
                        if jobs:
                            latest=jobs[0]
                            if latest['state']=='error':
                                self.report('backup','Сервер не создал резервную копию: '+str(latest.get('error',''))+'. Проверьте журнал резервирования в CRM.')
                            elif latest['state'] in ('queued','snapshot','files','checking','encrypting'):
                                labels={'queued':'ожидает','snapshot':'снимок БД','files':'копирование файлов',
                                    'checking':'проверка согласованности','encrypting':'шифрование'}
                                self.report('backup','Состояние на сервере: '+labels[latest['state']]+'.')
                        for meta in reversed(jobs):
                            if meta['state'] not in ('ready','downloading','verified'): continue
                            record=journal.get(meta['id'])
                            if record and record['state']=='deleted':continue
                            if record and record['state']=='verified' and meta['state']=='verified':
                                if pending and meta['id']==pending.get('job_id'):
                                    with self.request_lock:command_path.unlink(missing_ok=True)
                                continue
                            self.report('backup','Скачивание: '+meta['id'])
                            def progress(current,total):
                                if self.stop.is_set():raise InterruptedError('Загрузка приостановлена.')
                                self.report('backup',f'Скачано {current//1024} / {total//1024} КиБ')
                            path=download(meta,config['backup_folder'],journal,api.stream,
                                minimum_free_bytes=int(config.get('minimum_free_mb',512))*1024**2,
                                progress=progress)
                            api.confirm(meta)
                            if pending and meta['id']==pending.get('job_id'):
                                with self.request_lock:command_path.unlink(missing_ok=True)
                            self.report('backup','Сохранено и проверено SHA-256: '+path.name)
                            cleanup(config['backup_folder'],journal,keep=int(config.get('keep',7)),days=int(config.get('days',0)),
                                weekly=int(config.get('weekly',0)),enabled=config.get('cleanup_enabled',False))
                    else: self.report('backup','Резервирование выключено или устройство не подключено.')
                except Exception as exc: self.report('backup','Ошибка: '+type(exc).__name__+f' (HTTP {getattr(exc,"status",0)}). История сохранена.')
                self.stop.wait(15)
        finally: journal.close()

    def print_loop(self):
        while not self.stop.is_set():
            config=self.get_config()
            if not config.get('print_enabled'):
                self.report('print','Обработчик печати выключен.');self.stop.wait(3);continue
            try:
                self.print_session(config)
            except (Exception,SystemExit) as exc:
                self.report('print','Принтер уже обслуживается другим экземпляром.' if isinstance(exc,SystemExit) else
                    'Печать приостановлена: '+type(exc).__name__+f' (HTTP {getattr(exc,"status",0)}).')
                self.stop.wait(5)

    def print_session(self,config):
        from print_agent.driver import WindowsDriver
        from print_agent.transport import API
        from print_agent.journal import Journal
        from print_agent.engine import Engine
        from print_agent.profiles import printer_lock
        legacy=config.get('legacy_config')
        if legacy:
            path=Path(legacy);credentials=json.loads(path.read_text('utf-8-sig'));state=path.parent
        else:
            credentials={'server_url':config['server_url'],'agent_id':config['agent_id'],
                'token':config['print_token'],'printer_name':config['printer_name']}
            state=self.folder
        # При явном использовании старого профиля берём прежние lock и журнал.
        # Уже работающий старый агент не допускает вторую физическую печать.
        with exclusive(state/('agent.lock' if legacy else 'print.lock')), printer_lock(credentials['printer_name'],state):
            journal=Journal(state/'journal.sqlite3',credentials['agent_id'])
            try:
                engine=Engine(API(credentials,self.print_instance),journal,WindowsDriver(credentials['printer_name']),credentials['printer_name'])
                print_fields=('print_enabled','legacy_config','server_url','agent_id','print_token','printer_name')
                while not self.stop.is_set() and all(self.get_config().get(k)==config.get(k) for k in print_fields):
                    try:
                        engine.step();self.report('print','Принтер подключён: '+credentials['printer_name'])
                    except Exception as exc:
                        self.report('print','Ошибка: '+type(exc).__name__+f' (HTTP {getattr(exc,"status",0)}).')
                    self.stop.wait(3)
            finally: journal.close()
