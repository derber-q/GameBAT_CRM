"""Лёгкий Tk/ttk: сетевые/печатные операции отдельно от главного UI-потока."""
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import sys
import threading
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import uuid

from . import VERSION
from . import configuration as config_store
from .runtime import Runtime
from .transport import BackupAPI
from .journal import BackupJournal
from .downloads import verify_record, archive_folder
from .transport import error_message


class Application:
    def __init__(self,root,folder,profile,*,testing=False):
        self.root,self.folder,self.profile,self.testing=root,folder,profile,testing
        self.lock=threading.RLock();self.config=config_store.load(folder)
        self.runtime=Runtime(folder,self.current_config)
        self.root.title('ReSOURCE · Резервные копии');self.root.geometry('1080x780');self.root.minsize(920,690)
        style=ttk.Style(root);style.theme_use('clam')
        self.root.configure(background='#f3f6fa')
        style.configure('.',font=('Segoe UI',10),background='#f3f6fa',foreground='#23384d')
        style.configure('TButton',padding=(14,9));style.configure('TNotebook.Tab',padding=(22,10))
        style.configure('Primary.TButton',background='#247f91',foreground='white',font=('Segoe UI',11,'bold'))
        style.map('Primary.TButton',background=[('active','#196a7b'),('disabled','#adc0c7')])
        style.configure('Card.TFrame',background='white');style.configure('Card.TLabel',background='white')
        style.configure('Title.TLabel',font=('Segoe UI',20,'bold'),foreground='#16334b')
        style.configure('Muted.TLabel',foreground='#61758b')
        style.configure('Treeview',rowheight=34,background='white',fieldbackground='white',font=('Segoe UI',10))
        style.configure('Treeview.Heading',font=('Segoe UI',10,'bold'),padding=(10,8))
        ttk.Label(root,text='ReSOURCE · Защита данных',style='Title.TLabel').pack(anchor='w',padx=26,pady=(20,3))
        ttk.Label(root,text='Автоматические резервные копии CRM на вашем компьютере',style='Muted.TLabel').pack(anchor='w',padx=26)
        self.tabs=ttk.Notebook(root);self.tabs.pack(fill='both',expand=True,padx=14,pady=12)
        self.pages={name:ttk.Frame(self.tabs,padding=14) for name in ('Главная','Печать','Резервные копии','Настройки')}
        for name,frame in self.pages.items(): self.tabs.add(frame,text=name)
        self.print_status=tk.StringVar(value='Обработчик печати выключен.')
        self.backup_status=tk.StringVar(value='Резервирование выключено.')
        self.setup={}
        self.variables={}
        self.build_home();self.build_print();self.build_backups();self.build_settings()
        self.journal=BackupJournal(folder/'backups.sqlite3')
        self.refresh_history()
        self.tray=None
        self.root.protocol('WM_DELETE_WINDOW',self.hide)
        if not testing:
            self.install_tray();self.runtime.start();self.root.after(300,self.poll)

    def current_config(self):
        with self.lock: return dict(self.config)

    def status_label(self,parent,variable):
        ttk.Label(parent,textvariable=variable,wraplength=760).pack(anchor='w',pady=8)

    def build_home(self):
        frame=self.pages['Главная']
        card=ttk.Frame(frame,style='Card.TFrame',padding=24);card.pack(fill='x',pady=(0,14))
        self.overview=tk.StringVar(value='Проверяем подключение к CRM…')
        ttk.Label(card,textvariable=self.overview,style='Card.TLabel',font=('Segoe UI',17,'bold')).pack(anchor='w')
        self.connection=tk.StringVar(value=self.config['server_url'])
        ttk.Label(card,textvariable=self.connection,style='Card.TLabel').pack(anchor='w',pady=(8,12))
        self.steps=tk.StringVar();ttk.Label(card,textvariable=self.steps,style='Card.TLabel',justify='left').pack(anchor='w')
        row=ttk.Frame(card,style='Card.TFrame');row.pack(fill='x',pady=(20,0))
        self.home_backup_button=ttk.Button(row,text='Создать копию сейчас',style='Primary.TButton',command=self.request_backup)
        self.home_backup_button.pack(side='left')
        ttk.Button(row,text='Настроить резервное копирование',command=self.show_settings).pack(side='left',padx=10)
        card=ttk.Frame(frame,style='Card.TFrame',padding=24);card.pack(fill='x',pady=(0,14))
        ttk.Label(card,text='Последняя копия',style='Card.TLabel',font=('Segoe UI',12,'bold')).pack(anchor='w')
        self.last_copy=tk.StringVar(value='Первая копия ещё не создана.')
        ttk.Label(card,textvariable=self.last_copy,style='Card.TLabel',wraplength=880).pack(anchor='w',pady=8)
        ttk.Label(card,textvariable=self.backup_status,style='Card.TLabel',wraplength=880).pack(anchor='w')
        self.restore_status=tk.StringVar(value='Пробное восстановление ещё не выполнено.')
        proof=self.folder/'last-restore-check.json'
        if proof.is_file():
            try:self.restore_status.set('Восстановление проверено · '+self.display_date(json.loads(proof.read_text('utf-8'))['verified_at']))
            except (ValueError,KeyError):pass
        ttk.Label(card,textvariable=self.restore_status,style='Card.TLabel',wraplength=880).pack(anchor='w',pady=(8,0))
        ttk.Button(card,text='Посмотреть сохранённые копии',command=lambda:self.tabs.select(self.pages['Резервные копии'])).pack(anchor='w',pady=(14,0))
        self.space=tk.StringVar();self.status_label(frame,self.space)
        ttk.Label(frame,text='Ключ восстановления и пароль храните отдельно от CRM.\nКопия на внешнем диске дополнительно защищает от поломки компьютера.',
            style='Muted.TLabel',wraplength=880).pack(anchor='w',pady=8)

    def show_settings(self):self.tabs.select(self.pages['Настройки'])

    def update_overview(self):
        linked=bool(self.config.get('backup_token'))
        key=bool(self.setup.get('key_ready'))
        enabled=bool(self.setup.get('enabled') and self.config.get('backup_enabled'))
        self.steps.set(('✓ Компьютер подключён к CRM' if linked else '1. Подключите компьютер к CRM')+'\n\n'+
            ('✓ Ключ восстановления настроен' if key else '2. Создайте ключ восстановления и сохраните его в CRM')+'\n\n'+
            ('✓ Автоматические копии включены · '+str(self.setup.get('schedule_time',''))[:5]+' · '+self.setup.get('timezone','')
             if enabled else '3. Включите создание копий в CRM и получение на этом компьютере'))
        ready=linked and key and enabled and bool(self.setup.get('can_request'))
        self.home_backup_button.configure(state='normal' if ready else 'disabled')
        self.overview.set('Резервное копирование настроено' if ready else 'Нужно завершить настройку')
        rows=[row for row in self.journal.rows() if row['state']=='verified']
        if rows:
            meta=json.loads(rows[0]['meta'])
            self.last_copy.set('Сохранена и проверена · '+self.display_date(meta.get('snapshot_at'))+' · '+f"{meta.get('size',0)/1024**2:.1f} МБ")

    @staticmethod
    def display_date(value):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        try:return datetime.fromisoformat(value).astimezone(ZoneInfo('Europe/Moscow')).strftime('%d.%m.%Y %H:%M')
        except (TypeError,ValueError):return 'Дата не указана'

    def field(self,parent,name,label,*,boolean=False):
        ttk.Label(parent,text=label).pack(anchor='w',pady=(6,2))
        variable=tk.BooleanVar(value=bool(self.config.get(name))) if boolean else tk.StringVar(value=str(self.config.get(name,'')))
        self.variables[name]=variable
        widget=ttk.Checkbutton(parent,variable=variable,text='Включено') if boolean else ttk.Entry(parent,textvariable=variable)
        widget.pack(fill='x');return variable

    def build_print(self):
        frame=self.pages['Печать']
        self.field(frame,'printer_name','Принтер Windows')
        row=ttk.Frame(frame);row.pack(fill='x',pady=8)
        ttk.Button(row,text='Выбрать принтер',command=self.choose_printer).pack(side='left')
        ttk.Button(row,text='Проверить без печати',command=self.check_printer).pack(side='left',padx=7)
        self.field(frame,'print_enabled','Обработчик печати',boolean=True)
        ttk.Button(frame,text='Создать регистрацию печати',command=self.print_registration).pack(anchor='w',pady=8)
        ttk.Button(frame,text='Использовать прежний профиль Print Agent…',command=self.import_legacy).pack(anchor='w')
        ttk.Label(frame,text='Текущий принтер автоматически не переключается. Прежний агент нужно остановить\n'
            'штатно перед включением его профиля здесь. Журнал и блокировка сохраняются.',wraplength=730).pack(anchor='w',pady=10)
        self.status_label(frame,self.print_status)
        ttk.Button(frame,text='Сохранить настройки',command=self.save).pack(anchor='w')

    def build_backups(self):
        frame=self.pages['Резервные копии']
        ttk.Label(frame,text='Сохранённые резервные копии',font=('Segoe UI',15,'bold')).pack(anchor='w')
        self.status_label(frame,self.backup_status)
        self.tree=ttk.Treeview(frame,columns=('date','size','state','pin'),show='headings',height=9,selectmode='browse')
        for name,title,width in [('date','Дата копии · МСК',230),('size','Размер',130),('state','Результат проверки',250),('pin','Защита от удаления',190)]:
            self.tree.heading(name,text=title);self.tree.column(name,width=width,minwidth=50)
        self.tree.pack(fill='both',expand=True)
        row=ttk.Frame(frame);row.pack(fill='x',pady=8)
        ttk.Button(row,text='Создать копию сейчас',style='Primary.TButton',command=self.request_backup).pack(side='left',padx=2)
        ttk.Button(row,text='Открыть папку копий',command=self.open_folder).pack(side='left',padx=8)
        ttk.Button(row,text='Проверить восстановление',command=self.verify_restore).pack(side='left',padx=2)
        self.archive_tools=ttk.Frame(frame)
        ttk.Button(row,text='Дополнительные действия',command=lambda:self.toggle(self.archive_tools)).pack(side='right')
        for label,command in [('Проверить выбранный файл',self.verify),('Защитить / снять защиту',self.pin),('Удалить выбранную копию',self.delete),('Обновить список',self.refresh_history)]:
            ttk.Button(self.archive_tools,text=label,command=command).pack(side='left',padx=2)

    @staticmethod
    def toggle(frame):
        if frame.winfo_manager():frame.pack_forget()
        else:frame.pack(fill='x',pady=8)

    def build_settings(self):
        frame=self.pages['Настройки']
        left=ttk.Frame(frame);left.pack(side='left',fill='both',expand=True,padx=(0,24))
        right=ttk.Frame(frame);right.pack(side='left',fill='both',expand=True)
        ttk.Label(left,text='1. Подключение к CRM',font=('Segoe UI',13,'bold')).pack(anchor='w')
        self.field(left,'server_url','Адрес сайта CRM')
        self.field(left,'name','Название этого компьютера')
        ttk.Button(left,text='Открыть настройки в CRM',command=self.open_crm).pack(fill='x',pady=(10,4))
        ttk.Button(left,text='Подключить компьютер по коду…',command=self.enroll).pack(fill='x',pady=4)
        ttk.Label(left,text='Код нужен только при первом подключении или замене компьютера.',style='Muted.TLabel',wraplength=430).pack(anchor='w',pady=5)
        ttk.Label(left,text='2. Где хранить копии',font=('Segoe UI',13,'bold')).pack(anchor='w',pady=(20,0))
        self.field(left,'backup_folder','Папка резервных копий')
        ttk.Button(left,text='Выбрать папку…',command=self.pick_folder).pack(anchor='w',pady=8)
        self.field(left,'backup_enabled','Автоматически скачивать копии из CRM',boolean=True)
        self.field(left,'autostart','Запускать программу при входе в Windows',boolean=True)
        ttk.Label(right,text='3. Ключ восстановления',font=('Segoe UI',13,'bold')).pack(anchor='w')
        ttk.Label(right,text='Ключ нужен, чтобы восстановить CRM из архива.\nОн остаётся у владельца, а не на сервере.',style='Muted.TLabel',wraplength=430).pack(anchor='w',pady=10)
        ttk.Button(right,text='Создать ключ восстановления…',command=self.owner_key).pack(fill='x',pady=5)
        ttk.Button(right,text='Открыть папку ключа',command=self.open_recovery_folder).pack(fill='x',pady=5)
        ttk.Button(right,text='Скопировать публичный ключ для CRM',command=self.copy_public_key).pack(fill='x',pady=5)
        ttk.Button(right,text='Сохранить настройки',style='Primary.TButton',command=self.save).pack(fill='x',pady=(24,8))
        advanced=ttk.Frame(right)
        ttk.Button(right,text='Дополнительные настройки хранения',command=lambda:self.toggle(advanced)).pack(fill='x',pady=5)
        for name,label in [('keep','Оставлять последних ежедневных копий'),('days','Срок хранения, дней (0 — не ограничивать)'),
                           ('weekly','Дополнительных недельных копий'),('minimum_free_mb','Запас свободного места, МБ')]:self.field(advanced,name,label)
        self.field(advanced,'cleanup_enabled','Автоматически удалять старые копии',boolean=True)
        ttk.Button(right,text='Завершить программу',command=self.quit).pack(anchor='w',pady=12)

    def open_crm(self):
        import webbrowser
        from print_agent.transport import server_origin
        webbrowser.open(server_origin(self.variables['server_url'].get())+'/crm/backups/')

    def open_recovery_folder(self):
        value=self.config.get('recovery_key_path')
        if value and Path(value).is_file():os.startfile(str(Path(value).parent))
        else:messagebox.showinfo('Ключ восстановления','Сначала создайте ключ восстановления.')

    def copy_public_key(self):
        value=self.config.get('recovery_public_path')
        if not value or not Path(value).is_file():
            messagebox.showinfo('Ключ восстановления','Сначала создайте ключ восстановления.');return
        self.root.clipboard_clear();self.root.clipboard_append(Path(value).read_text('ascii'))
        messagebox.showinfo('Публичный ключ','Публичный ключ скопирован. Вставьте его в настройки резервного копирования CRM.')

    def save(self):
        try:
            values={name:variable.get() for name,variable in self.variables.items()}
            for name in ('keep','days','weekly','minimum_free_mb'):
                values[name]=int(values[name])
                if not 0<=values[name]<=100000: raise ValueError('Недопустимая настройка хранения.')
            folder=archive_folder(values['backup_folder'])
            if folder.parent==folder or folder.resolve().is_relative_to(Path(sys.executable).parent.resolve()):
                raise ValueError('Папка архивов не должна быть каталогом установки.')
            if any((p/'.git').exists() for p in (folder,*folder.parents)):
                raise ValueError('Нельзя сохранять архивы в Git-репозитории.')
            if folder.is_relative_to(Path(tempfile.gettempdir()).resolve()) or any(p.name.casefold()=='protected_media' for p in (folder,*folder.parents)):
                raise ValueError('Временные каталоги и исходные медиа CRM не подходят для хранения архивов.')
            with self.lock:
                changed={**self.config,**values}
                if changed.get('legacy_config'):
                    legacy=json.loads(Path(changed['legacy_config']).read_text('utf-8-sig'))
                    if changed['printer_name']!=legacy['printer_name']:
                        raise ValueError('Прежний профиль сохраняет свой принтер. Для другого принтера создайте новый профиль.')
                # Адрес не меняется вместе с секретами: новое подключение должно
                # быть явно зарегистрировано, без отправки старого токена чужому серверу.
                if changed['server_url'].rstrip('/')!=self.config['server_url'].rstrip('/') and (self.config.get('backup_token') or self.config.get('print_token')):
                    raise ValueError('Для другого сервера создайте новый профиль; ключи не переносятся автоматически.')
                if changed['autostart']!=self.config.get('autostart',False): self.autostart(changed['autostart'])
                config_store.save(self.folder,changed);self.config=changed
            self.connection.set(changed['server_url']);self.refresh_history()
            return True
        except Exception as exc: messagebox.showerror('Настройки',str(exc));return False

    def background(self,function,channel='backup'):
        def run():
            try: function()
            except Exception as exc:self.runtime.report(channel,error_message(exc))
        threading.Thread(target=run,daemon=True).start()

    def enroll(self):
        if not self.save():return
        code=simpledialog.askstring('Резервное устройство','Одноразовый код из административной страницы CRM:',show='*')
        if not code:return
        def perform():
            config=self.current_config();config['device_id']=str(uuid.uuid4());config['backup_token']=config_store.new_secret()
            result=BackupAPI(config,self.runtime.session).request('enroll/',{'code':code,'device_id':config['device_id'],
                'token_hash':hashlib.sha256(config['backup_token'].encode()).hexdigest(),'name':config['name']})
            if result.get('device_id')!=config['device_id']:raise ValueError('Неверный ответ регистрации.')
            with self.lock: config_store.save(self.folder,config);self.config=config
            self.runtime.report('backup','Устройство подключено. Включите получение резервных копий в настройках.')
        self.background(perform)

    def request_backup(self):
        if not self.config.get('backup_token') or not self.config.get('backup_enabled'):
            messagebox.showinfo('Резервирование','Сначала подключите устройство и включите резервирование.');return
        try:
            self.runtime.request_backup();self.backup_status.set('Запрос поставлен в очередь.')
        except Exception as exc:messagebox.showerror('Резервирование','Запрос не сохранён: '+type(exc).__name__)

    def selected(self):
        selected=self.tree.selection()
        return self.journal.get(selected[0]) if selected else None

    def refresh_history(self):
        self.tree.delete(*self.tree.get_children())
        states={'downloading':'Скачивается','checking':'Проверяется','verified':'Сохранена','error':'Ошибка','publishing':'Завершается','deleted':'Удалена','corrupt':'Повреждена'}
        for row in self.journal.rows():
            meta=json.loads(row['meta'])
            self.tree.insert('',tk.END,iid=row['id'],values=(self.display_date(meta.get('snapshot_at')),
                f"{meta.get('size',0)/1024**2:.1f} МБ",states.get(row['state'],row['state']),
                'Защищена' if row['pinned'] else 'По правилам хранения'))
        try:
            folder=archive_folder(self.config['backup_folder']);usage=shutil.disk_usage(folder)
            total=sum(Path(row['path']).stat().st_size for row in self.journal.rows() if Path(row['path']).is_file())
            self.space.set(f'Свободно {usage.free//1024**3} ГиБ · архивы {total//1024**2} МиБ')
        except OSError:self.space.set('Папка архивов недоступна.')
        self.update_overview()

    def verify(self):
        row=self.selected()
        if row:
            def check():
                matches=verify_record(row,self.config['backup_folder'])
                if not matches:self.journal.put(json.loads(row['meta']),row['path'],'corrupt','sha256_failed')
                self.runtime.report('backup','Проверка SHA-256: '+('совпадает' if matches else 'ОШИБКА, копия помечена повреждённой'))
            self.background(check)

    def verify_restore(self):
        row=self.selected() or next((item for item in self.journal.rows() if item['state']=='verified'),None)
        if not row:
            messagebox.showinfo('Проверка восстановления','Сначала создайте и скачайте первую копию.');return
        config=self.current_config()
        if not config.get('recovery_key_path'):
            messagebox.showinfo('Проверка восстановления','Сначала создайте ключ восстановления в настройках.');return
        password=config.get('recovery_password') or simpledialog.askstring('Проверка восстановления','Пароль ключа восстановления:',show='●')
        if not password:return
        self.restore_status.set('Проверяем восстановление в отдельной папке. Рабочая CRM продолжает работу…')
        def perform():
            from .recovery import verify_restore
            proof=verify_restore(row,config,self.folder,password)
            self.runtime.report('restore',proof)
        self.background(perform)

    def pin(self):
        row=self.selected()
        if row:self.journal.pin(row['id'],not row['pinned']);self.refresh_history()

    def delete(self):
        row=self.selected()
        if not row:return
        verified=sorted((r for r in self.journal.rows() if r['state']=='verified'),key=lambda r:r['verified_at'],reverse=True)
        if row['pinned'] or (verified and verified[0]['id']==row['id']):
            messagebox.showinfo('Удаление','Закреплённую или последнюю проверенную копию удалить нельзя.');return
        path=Path(row['path']);folder=archive_folder(self.config['backup_folder'])
        owned_partial=(row['state']=='error' and path.parent==folder and path.name==row['id']+'.partial'
            and path.is_file() and not path.is_symlink() and path.stat().st_nlink==1)
        owned_corrupt=(row['state']=='corrupt' and path.parent==folder and path.name.endswith('_'+row['id']+'.backup')
            and path.resolve()==path.absolute() and path.is_file() and not path.is_symlink() and path.stat().st_nlink==1)
        if not owned_partial and not owned_corrupt and (row['state']!='verified' or not verify_record(row,folder)):return
        if messagebox.askyesno('Удаление','Удалить выбранный проверенный архив?'):
            Path(row['path']).unlink();self.journal.put(json.loads(row['meta']),row['path'],'deleted');self.refresh_history()

    def pick_folder(self):
        value=filedialog.askdirectory()
        if value:self.variables['backup_folder'].set(value)

    def open_folder(self):
        os.startfile(str(archive_folder(self.config['backup_folder'])))

    def choose_printer(self):
        import win32print
        printers=win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL|win32print.PRINTER_ENUM_CONNECTIONS,None,2)
        window=tk.Toplevel(self.root);window.title('Выбрать принтер')
        selector=ttk.Combobox(window,values=[p['pPrinterName'] for p in printers],state='readonly',width=60);selector.pack(padx=20,pady=20)
        def select():self.variables['printer_name'].set(selector.get());window.destroy()
        ttk.Button(window,text='Выбрать',command=select).pack(pady=10)

    def check_printer(self):
        printer=self.variables['printer_name'].get()
        def check():
            from print_agent.driver import WindowsDriver
            self.runtime.report('print','Принтер '+('доступен' if WindowsDriver(printer).available() else 'недоступен'))
        self.background(check,channel='print')

    def print_registration(self):
        if self.config.get('legacy_config'):
            messagebox.showinfo('Прежний профиль','Прежний агент уже зарегистрирован. Для другого принтера создайте новый профиль.')
            return
        if not self.save():return
        with self.lock:
            config=dict(self.config)
            config['print_token']=config.get('print_token') or config_store.new_secret()
            config_store.save(self.folder,config);self.config=config
        value={'id':config['agent_id'],'name':config['name'],'printer_name':config['printer_name'],
            'token_hash':hashlib.sha256(config['print_token'].encode()).hexdigest()}
        target=filedialog.asksaveasfilename(defaultextension='.json',initialfile='print-registration.json')
        if target:Path(target).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

    def import_legacy(self):
        path=filedialog.askopenfilename(title='Прежний config.json Print Agent',filetypes=[('JSON','*.json')])
        if path and messagebox.askyesno('Прежняя печать','Использовать прежний журнал и блокировку без переноса файлов?\nСначала штатно остановите прежний агент.'):
            legacy=json.loads(Path(path).read_text('utf-8-sig'))
            self.variables['printer_name'].set(legacy['printer_name'])
            with self.lock:
                self.config['legacy_config']=path;self.config['printer_name']=legacy['printer_name'];config_store.save(self.folder,self.config)
            self.print_status.set('Прежний профиль выбран. Включите обработчик после остановки прежнего агента.')

    def owner_key(self):
        from .key_dialog import show
        show(self)

    def autostart(self,enabled):
        import winreg
        from subprocess import list2cmdline
        if enabled and not messagebox.askyesno('Автозапуск','Запускать этот профиль при входе в Windows?'):raise ValueError('Автозапуск не разрешён.')
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
            name='ReSOURCE Local Agent '+self.profile
            if enabled:
                command=[sys.executable]+([] if getattr(sys,'frozen',False) else ['-m','local_agent'])+['--profile',self.profile,'--background']
                winreg.SetValueEx(key,name,0,winreg.REG_SZ,list2cmdline(command))
            else:
                try:winreg.DeleteValue(key,name)
                except FileNotFoundError:pass

    def new_profile(self):
        import subprocess
        profile='printer-'+uuid.uuid4().hex[:8]
        command=[sys.executable]+([] if getattr(sys,'frozen',False) else ['-m','local_agent'])+['--profile',profile]
        subprocess.Popen(command,creationflags=subprocess.CREATE_NO_WINDOW)

    def install_tray(self):
        import pystray
        from PIL import Image,ImageDraw
        image=Image.new('RGBA',(64,64),'#207e91');draw=ImageDraw.Draw(image);draw.text((17,17),'RS',fill='white',stroke_width=1)
        self.tray=pystray.Icon('resource-'+self.profile,image,'ReSOURCE · '+self.profile,
            pystray.Menu(pystray.MenuItem('Открыть',lambda *_:self.runtime.report('ui','show'),default=True),
                         pystray.MenuItem('Завершить',lambda *_:self.runtime.report('ui','quit'))))
        threading.Thread(target=self.tray.run,daemon=True).start()

    def hide(self):
        if self.tray:self.root.withdraw()
        else:self.quit()

    def poll(self):
        while True:
            try:channel,text=self.runtime.events.get_nowait()
            except queue.Empty:break
            if channel=='ui':
                if text=='quit':self.quit();return
                self.root.deiconify();self.root.lift()
            elif channel=='print':self.print_status.set(text)
            elif channel=='backup_setup':
                self.setup=text;self.update_overview()
            elif channel=='restore':
                self.restore_status.set('Восстановление проверено · '+self.display_date(text['verified_at']))
                self.backup_status.set('Копия восстановлена в отдельную папку. Файлы, база и ключи проверены.')
            else:
                self.backup_status.set(text)
                if text.startswith(('Сохранено','Проверка SHA-256:')):self.refresh_history()
        self.root.after(300,self.poll)

    def quit(self):
        self.runtime.stop.set()
        if any(thread.is_alive() for thread in self.runtime.threads):
            self.backup_status.set('Завершение текущей операции. Не закрывайте Windows принудительно.')
            self.root.after(300,self.quit);return
        if self.tray:self.tray.stop()
        self.journal.close();self.root.destroy()
