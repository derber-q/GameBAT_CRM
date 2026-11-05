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


class Application:
    def __init__(self,root,folder,profile,*,testing=False):
        self.root,self.folder,self.profile,self.testing=root,folder,profile,testing
        self.lock=threading.RLock();self.config=config_store.load(folder)
        self.runtime=Runtime(folder,self.current_config)
        self.root.title('ReSOURCE Local Agent · '+profile);self.root.geometry('880x620');self.root.minsize(720,520)
        style=ttk.Style(root);style.theme_use('clam')
        style.configure('TButton',padding=(10,7));style.configure('TNotebook.Tab',padding=(16,8))
        ttk.Label(root,text='ReSOURCE Local Agent',font=('Segoe UI',17,'bold'),foreground='#207e91').pack(anchor='w',padx=18,pady=(15,3))
        ttk.Label(root,text=f'Версия {VERSION} · профиль {profile}').pack(anchor='w',padx=18)
        self.tabs=ttk.Notebook(root);self.tabs.pack(fill='both',expand=True,padx=14,pady=12)
        self.pages={name:ttk.Frame(self.tabs,padding=14) for name in ('Главная','Печать','Резервные копии','Настройки')}
        for name,frame in self.pages.items(): self.tabs.add(frame,text=name)
        self.print_status=tk.StringVar(value='Обработчик печати выключен.')
        self.backup_status=tk.StringVar(value='Резервирование выключено.')
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
        ttk.Label(frame,text=self.config['name'],font=('Segoe UI',13,'bold')).pack(anchor='w')
        self.connection=tk.StringVar(value=self.config['server_url']);self.status_label(frame,self.connection)
        self.status_label(frame,self.print_status);self.status_label(frame,self.backup_status)
        self.space=tk.StringVar();self.status_label(frame,self.space)
        ttk.Label(frame,text='Архив на том же физическом диске не защищает от отказа диска.\n'
            'Приватный ключ восстановления храните отдельно; потерянный ключ нельзя заменить токеном устройства.',
            wraplength=750,foreground='#8c590b').pack(anchor='w',pady=18)
        ttk.Button(frame,text='Создать ещё один профиль',command=self.new_profile).pack(anchor='w')

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
        self.status_label(frame,self.backup_status)
        self.tree=ttk.Treeview(frame,columns=('date','download','version','size','state','check','pin'),show='headings',height=10,selectmode='browse')
        for name,title,width in [('date','Дата снимка',160),('download','Скачана',150),('version','Версия',65),('size','МиБ',65),('state','Состояние',100),('check','SHA-256',85),('pin','Закреплена',75)]:
            self.tree.heading(name,text=title);self.tree.column(name,width=width,minwidth=50)
        self.tree.pack(fill='both',expand=True)
        row=ttk.Frame(frame);row.pack(fill='x',pady=8)
        for label,command in [('Создать и скачать сейчас',self.request_backup),('Проверить SHA-256',self.verify),
            ('Закрепить / снять',self.pin),('Удалить',self.delete),('Обновить',self.refresh_history)]:
            ttk.Button(row,text=label,command=command).pack(side='left',padx=2)
        ttk.Button(frame,text='Открыть папку архивов',command=self.open_folder).pack(anchor='w')

    def build_settings(self):
        frame=self.pages['Настройки']
        left=ttk.Frame(frame);left.pack(side='left',fill='both',expand=True,padx=(0,15))
        right=ttk.Frame(frame);right.pack(side='left',fill='both',expand=True)
        for name,label in [('server_url','Адрес CRM (HTTPS или loopback HTTP)'),('name','Название установки'),
                           ('backup_folder','Папка архивов'),('keep','Последних ежедневных копий'),
                           ('days','Срок хранения, дней'),('weekly','Дополнительных недельных копий'),
                           ('minimum_free_mb','Минимум свободного места, МиБ')]: self.field(left,name,label)
        for name,label in [('backup_enabled','Получать резервные копии'),('cleanup_enabled','Автоматическая очистка'),
                           ('autostart','Автозапуск при входе Windows')]: self.field(right,name,label,boolean=True)
        for label,command in [('Подключить резервное устройство…',self.enroll),('Выбрать папку…',self.pick_folder),
            ('Создать ключ восстановления владельца…',self.owner_key),('Сохранить настройки',self.save),
            ('Завершить программу',self.quit)]: ttk.Button(right,text=label,command=command).pack(fill='x',pady=6)
        ttk.Label(right,text='Расписание создания снимков задаётся в CRM.\n'
            'Здесь включается только получение готовых архивов.\n'
            'Токены защищены DPAPI текущего пользователя Windows.',wraplength=325).pack(anchor='w',pady=10)

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
            except Exception as exc: self.runtime.report(channel,'Ошибка: '+type(exc).__name__+f' (HTTP {getattr(exc,"status",0)}).')
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
            self.tree.insert('',tk.END,iid=row['id'],values=(meta.get('snapshot_at',''),(row.get('verified_at') or '')[:19],meta.get('version','')[:7],
                f"{meta.get('size',0)/1024**2:.2f}",states.get(row['state'],row['state']),
                'Совпадает' if row['state']=='verified' else ('Ошибка' if row['state']=='corrupt' else '—'),'Да' if row['pinned'] else 'Нет'))
        try:
            folder=archive_folder(self.config['backup_folder']);usage=shutil.disk_usage(folder)
            total=sum(Path(row['path']).stat().st_size for row in self.journal.rows() if Path(row['path']).is_file())
            self.space.set(f'Свободно {usage.free//1024**3} ГиБ · архивы {total//1024**2} МиБ')
        except OSError:self.space.set('Папка архивов недоступна.')

    def verify(self):
        row=self.selected()
        if row:
            def check():
                matches=verify_record(row,self.config['backup_folder'])
                if not matches:self.journal.put(json.loads(row['meta']),row['path'],'corrupt','sha256_failed')
                self.runtime.report('backup','Проверка SHA-256: '+('совпадает' if matches else 'ОШИБКА, копия помечена повреждённой'))
            self.background(check)

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
        from crm_backups.crypto import generate_keys
        password=simpledialog.askstring('Ключ владельца','Пароль приватного ключа (не менее 12 символов):',show='*')
        if not password:return
        confirmation=simpledialog.askstring('Ключ владельца','Повторите пароль приватного ключа:',show='*')
        if password!=confirmation:
            messagebox.showerror('Ключ','Пароли не совпадают. Ключ не создан.');return
        path=filedialog.asksaveasfilename(defaultextension='.recovery.pem',initialfile='ReSOURCE.recovery.pem')
        if not path:return
        try:
            private,public=generate_keys(password.encode())
            with Path(path).open('xb') as stream:
                config_store.private_file(path);stream.write(private);stream.flush();os.fsync(stream.fileno())
            with Path(path+'.public.pem').open('xb') as stream:stream.write(public)
            messagebox.showinfo('Ключ владельца','Сохраните ещё одну копию приватного ключа отдельно от CRM и этого диска.\n'
                'В CRM передайте только файл .public.pem. Потеря ключа/пароля делает архивы нечитаемыми.')
        except Exception as exc:messagebox.showerror('Ключ',type(exc).__name__)

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
